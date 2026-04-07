import json
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

class SearchMethod(Enum):
    KEYWORD = "keyword"
    RAG = "rag"
    HYBRID = "hybrid"

@dataclass
class SearchResult:
    id: str
    name: str
    role: str
    score: float
    method: SearchMethod
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class QueryAnalysis:
    original_query: str
    recommended_method: SearchMethod
    keywords: List[str]
    confidence: float
    reasoning: str

class HybridSearchService:
    def __init__(self, sn_conn, neo4j_driver):
        self.sn_conn = sn_conn
        self.neo4j_driver = neo4j_driver

    # =========================================================================
    # 1. QUERY ANALYSIS (The "Brain")
    # =========================================================================
    def analyze_query(self, query: str) -> QueryAnalysis:
        # 1. Stricter Prompting for Classification
        prompt = f"""
        Analyze this survival network query: "{query}"
        
        CLASSIFICATION RULES:
        - KEYWORD: Use if the user is looking for a specific Name, Role Title, or Exact Filter (e.g., "Find Mari", "List all Delivery Riders", "Who is Jino?").
        - RAG: Use if the user describes a problem, skill, or abstract need without naming a specific role or person (e.g., "Who can fix injuries?", "I need help with bleeding", "How to survive a collapse?").
        - HYBRID: Use ONLY if the query combines a specific filter with an abstract need (e.g., "Find a Delivery Rider who knows first aid").

        Return JSON only:
        {{"method": "keyword"|"rag"|"hybrid", "keywords": ["names_or_titles_only"], "confidence": <float>, "reasoning": "short explanation"}}
        """
        
        with self.sn_conn.cursor() as cur:
            cur.execute("SELECT SNOWFLAKE.CORTEX.COMPLETE('snowflake-arctic', %s)", (prompt,))
            raw = cur.fetchone()[0]
            
            clean_json = raw.strip().replace("```json", "").replace("```", "")
            try:
                parsed = json.loads(clean_json)
            except:
                # Fallback simple parser for LLM quirks
                start, end = clean_json.find('{'), clean_json.rfind('}')
                parsed = json.loads(clean_json[start:end+1]) if start != -1 else {"method": "hybrid", "confidence": 0.5, "keywords": []}

        # 2. Refined Heuristic Indicators (Less Overlap)
        qlow = query.lower()
        
        # Keyword indicators focus on specific identifiers; include language
        # qualifiers (e.g., 'francophone') so queries with language filters
        # are treated as keyword-like filters when appropriate.
        keyword_indicators = [
            'role', 'name', 'title', 'exact', 'list all',
            'francophone', 'french', 'spanish', 'english', 'bilingual', 'language', 'located', 'near', 'who is', 'find'
        ]
        # RAG indicators focus on verbs and needs
        # In hybrid_search_service.py -> analyze_query
        rag_indicators = [
            'how', 'who can', 'fix', 'treat', 'injury', 'similar', 'assist', 'help out', 'guide', 'protect',
            'skills', 'siblings', 'family', 'related', 'brother', 'sister' # Add these
        ]

        kw_score = sum(1 for k in keyword_indicators if k in qlow)
        rag_score = sum(1 for r in rag_indicators if r in qlow)

        # 3. "Winner Takes All" Decision Logic
        model_method_str = str(parsed.get('method', 'hybrid')).lower()
        
        # If the query is clearly one type based on keywords, prefer the
        # heuristic decision; otherwise fall back to the model's choice.
        if kw_score > 0 and rag_score == 0:
            final_method = SearchMethod.KEYWORD
        elif rag_score > 0 and kw_score == 0:
            final_method = SearchMethod.RAG
        elif kw_score > 0 and rag_score > 0:
            final_method = SearchMethod.HYBRID
        else:
            # Fallback to model's choice for mixed or complex queries
            try:
                final_method = SearchMethod(model_method_str)
            except:
                final_method = SearchMethod.HYBRID

        # Reconcile with the reasoning text if the model included an explicit
        # classification in its explanation (helps when model returns the
        # wrong 'method' field but explains correctly).
        reasoning_text = str(parsed.get('reasoning', '')).lower()
        if 'hybrid' in reasoning_text and final_method != SearchMethod.HYBRID:
            final_method = SearchMethod.HYBRID
        elif 'keyword' in reasoning_text and final_method != SearchMethod.KEYWORD:
            final_method = SearchMethod.KEYWORD
        elif 'rag' in reasoning_text and final_method != SearchMethod.RAG:
            final_method = SearchMethod.RAG

        return QueryAnalysis(
            original_query=query,
            recommended_method=final_method,
            keywords=parsed.get('keywords', []),
            confidence=float(parsed.get('confidence', 0.8)),
            reasoning=parsed.get('reasoning', "Analyzed intent based on terminology.")
        )

    # =========================================================================
    # 2. KEYWORD SEARCH (Snowflake)
    # =========================================================================
    def keyword_search(self, analysis: QueryAnalysis, limit: int = 10) -> List[SearchResult]:
        results = []
        # If no keywords extracted, use the whole query as the search term
        search_term = analysis.keywords[0] if analysis.keywords else analysis.original_query
            
        with self.sn_conn.cursor() as cur:
            cur.execute("""
                SELECT NAME, ROLE, SPECIAL 
                FROM SURVIVORS 
                WHERE NAME ILIKE %s OR ROLE ILIKE %s OR SPECIAL ILIKE %s
                LIMIT %s
            """, (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%", limit))
            
            for name, role, special in cur.fetchall():
                results.append(SearchResult(
                    id=name, name=name, role=role, score=1.0, 
                    method=SearchMethod.KEYWORD, details={"special": special}
                ))
        return results

    # =========================================================================
    # 3. RAG SEARCH (Snowflake + Neo4j)
    # =========================================================================
    def rag_search(self, query: str, limit: int = 10) -> List[SearchResult]:
        with self.sn_conn.cursor() as cur:
            cur.execute("SELECT SNOWFLAKE.CORTEX.EMBED_TEXT_768('snowflake-arctic-embed-m', %s)", (query,))
            vector = cur.fetchone()[0]
            
        results = []
        with self.neo4j_driver.session() as session:
            rows = session.run("""
                CALL db.index.vector.queryNodes('survivor_embeddings', $limit, $vector)
                YIELD node, score 
                RETURN node.name AS name, node.role AS role, node.special AS special, score
            """, vector=vector, limit=limit)
            
            for r in rows:
                results.append(SearchResult(
                    id=r['name'], name=r['name'], role=r['role'], score=r['score'], 
                    method=SearchMethod.RAG, details={"special": r['special']}
                ))
        return results

    # =========================================================================
    # 4. HYBRID MERGE (Reciprocal Rank Fusion)
    # =========================================================================
    def hybrid_search(self, query: str, analysis: QueryAnalysis, limit: int = 10) -> List[SearchResult]:
        kw_results = self.keyword_search(analysis, limit)
        rag_results = self.rag_search(query, limit)
        
        K = 60
        combined_scores = {}
        all_results = {res.id: res for res in kw_results + rag_results}
        
        for rank, res in enumerate(kw_results):
            combined_scores[res.id] = combined_scores.get(res.id, 0) + (1.0 / (K + rank + 1))
        for rank, res in enumerate(rag_results):
            combined_scores[res.id] = combined_scores.get(res.id, 0) + (1.0 / (K + rank + 1))
            
        sorted_ids = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        
        final_results = []
        if sorted_ids:
            max_rrf = sorted_ids[0][1]
            for surv_id, rrf_score in sorted_ids[:limit]:
                res = all_results[surv_id]
                res.score = (rrf_score / max_rrf)
                res.method = SearchMethod.HYBRID
                final_results.append(res)
            
        return final_results

    def smart_search(self, query: str, limit: int = 10):
        analysis = self.analyze_query(query)
        
        if analysis.recommended_method == SearchMethod.KEYWORD:
            results = self.keyword_search(analysis, limit)
        elif analysis.recommended_method == SearchMethod.RAG:
            results = self.rag_search(query, limit)
        else:
            results = self.hybrid_search(query, analysis, limit)
            
        return {
            "query": query,
            "method_used": analysis.recommended_method.value,
            "analysis": analysis,
            "results": results
        }