"""Shared State feature."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
import re
import neo4j
import snowflake.connector

from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google.adk.agents import LlmAgent, Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools import ToolContext
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = None


def get_neo4j_driver():
    global driver
    if driver is None and NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD),
        )
    return driver


class ProverbsState(BaseModel):
    """List of the proverbs being written."""

    proverbs: list[str] = Field(
        default_factory=list,
        description="The list of already written proverbs",
    )


def set_proverbs(tool_context: ToolContext, new_proverbs: list[str]) -> Dict[str, str]:
    """
    Set the list of provers using the provided new list.

    Args:
        "new_proverbs": {
            "type": "array",
            "items": {"type": "string"},
            "description": "The new list of proverbs to maintain",
        }

    Returns:
        Dict indicating success status and message
    """
    try:
        # Put this into a state object just to confirm the shape
        new_state = {"proverbs": new_proverbs}
        tool_context.state["proverbs"] = new_state["proverbs"]
        return {"status": "success", "message": "Proverbs updated successfully"}

    except Exception as e:
        return {"status": "error", "message": f"Error updating proverbs: {str(e)}"}


def get_weather(tool_context: ToolContext, location: str) -> Dict[str, str]:
    """Get the weather for a given location. Ensure location is fully spelled out."""
    return {"status": "success", "message": f"The weather in {location} is sunny."}


def on_before_agent(callback_context: CallbackContext):
    """
    Initialize proverbs state if it doesn't exist.
    """

    if "proverbs" not in callback_context.state:
        # Initialize with default recipe
        default_proverbs = []
        callback_context.state["proverbs"] = default_proverbs

    return None


# --- Define the Callback Function ---
#  modifying the agent's system prompt to incude the current state of the proverbs list
def before_model_modifier(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """Inspects/modifies the LLM request or skips the call."""
    agent_name = callback_context.agent_name
    if agent_name == "ProverbsAgent":
        proverbs_json = "No proverbs yet"
        if (
            "proverbs" in callback_context.state
            and callback_context.state["proverbs"] is not None
        ):
            try:
                proverbs_json = json.dumps(callback_context.state["proverbs"], indent=2)
            except Exception as e:
                proverbs_json = f"Error serializing proverbs: {str(e)}"
        # --- Modification Example ---
        # Add a prefix to the system instruction
        original_instruction = llm_request.config.system_instruction or types.Content(
            role="system", parts=[]
        )
        prefix = f"""You are a helpful assistant for maintaining a list of proverbs.
        This is the current state of the list of proverbs: {proverbs_json}
        When you modify the list of proverbs (wether to add, remove, or modify one or more proverbs), use the set_proverbs tool to update the list."""
        # Ensure system_instruction is Content and parts list exists
        if not isinstance(original_instruction, types.Content):
            # Handle case where it might be a string (though config expects Content)
            original_instruction = types.Content(
                role="system", parts=[types.Part(text=str(original_instruction))]
            )
        if not original_instruction.parts:
            original_instruction.parts = [types.Part(text="")]

        # Modify the text of the first part
        if original_instruction.parts and len(original_instruction.parts) > 0:
            modified_text = prefix + (original_instruction.parts[0].text or "")
            original_instruction.parts[0].text = modified_text
        llm_request.config.system_instruction = original_instruction

    return None


def simple_after_model_modifier(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> Optional[LlmResponse]:
    """Stop the consecutive tool calling of the agent"""
    agent_name = callback_context.agent_name
    # --- Inspection ---
    if agent_name == "ProverbsAgent":
        if llm_response.content and llm_response.content.parts:
            # Assuming simple text response for this example
            if (
                llm_response.content.role == "model"
                and llm_response.content.parts[0].text
            ):
                callback_context._invocation_context.end_invocation = True

        elif llm_response.error_message:
            return None
        else:
            return None  # Nothing to modify
    return None


# --- Inlined tools and agent from agentImportedFromADK ---

# Snowflake helper using environment variables
SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER")
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")
SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE")
SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE")
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA")

def get_snowflake_conn():
    if not (SNOWFLAKE_USER and SNOWFLAKE_PASSWORD and SNOWFLAKE_ACCOUNT):
        return None
    try:
        return snowflake.connector.connect(
            user=SNOWFLAKE_USER,
            password=SNOWFLAKE_PASSWORD,
            account=SNOWFLAKE_ACCOUNT,
            warehouse=SNOWFLAKE_WAREHOUSE,
            database=SNOWFLAKE_DATABASE,
            schema=SNOWFLAKE_SCHEMA,
        )
    except Exception:
        return None

# Use the existing Neo4j driver getter for service-level use
neo4j_driver = get_neo4j_driver()
sn_conn = get_snowflake_conn()

_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _validate_identifier(value: str, field_name: str) -> str:
    if not value or not _IDENTIFIER_RE.match(value):
        raise ValueError(f"Invalid {field_name}: {value!r}")
    return value


def _normalize_relationships(relationships: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not relationships:
        return []
    if not isinstance(relationships, list):
        raise ValueError("relationships must be a list of relationship descriptors")
    return relationships


async def upsert_data_node_from_graph(
    node_label: str,
    properties: Dict[str, Any],
    key_property: str = "id",
    relationships: Optional[List[Dict[str, Any]]] = None,
) -> str:
    try:
        node_label = _validate_identifier(node_label, "node_label")
        key_property = _validate_identifier(key_property, "key_property")
        relationships = _normalize_relationships(relationships)

        if not isinstance(properties, dict) or not properties:
            return "Error creating data node: properties must be a non-empty dictionary."

        node_key = properties.get(key_property)
        property_keys = sorted(properties.keys())

        if neo4j_driver is None:
            return "Error creating data node: Neo4j not configured."

        with neo4j_driver.session() as session:
            if node_key is not None:
                node_query = f"""
                MERGE (n:{node_label} {{{key_property}: $node_key}})
                SET n += $properties
                RETURN elementId(n) AS node_id, n.{key_property} AS node_key
                """
                node_record = session.run(
                    node_query,
                    node_key=node_key,
                    properties=properties,
                ).single()
            else:
                node_query = f"""
                CREATE (n:{node_label})
                SET n += $properties
                RETURN elementId(n) AS node_id, n.{key_property} AS node_key
                """
                node_record = session.run(
                    node_query,
                    properties=properties,
                ).single()

            if not node_record:
                return f"Error creating data node: unable to persist {node_label}."

            created_relationships: List[str] = []
            for relationship in relationships:
                target_label = _validate_identifier(str(relationship.get("target_label", "")), "target_label")
                match_property = _validate_identifier(str(relationship.get("match_property", "")), "match_property")
                relationship_type = _validate_identifier(str(relationship.get("relationship_type", "")), "relationship_type")
                match_value = relationship.get("match_value")
                direction = str(relationship.get("direction", "out")).lower()

                if match_value is None:
                    raise ValueError("relationship descriptor missing match_value")
                if direction not in {"out", "in"}:
                    raise ValueError("direction must be 'out' or 'in'")

                if direction == "out":
                    rel_query = f"""
                    MATCH (n:{node_label} {{{key_property}: $node_key}})
                    MATCH (target:{target_label} {{{match_property}: $match_value}})
                    MERGE (n)-[:{relationship_type}]->(target)
                    RETURN target.{match_property} AS target_value
                    """
                else:
                    rel_query = f"""
                    MATCH (n:{node_label} {{{key_property}: $node_key}})
                    MATCH (target:{target_label} {{{match_property}: $match_value}})
                    MERGE (target)-[:{relationship_type}]->(n)
                    RETURN target.{match_property} AS target_value
                    """

                rel_record = session.run(
                    rel_query,
                    node_key=node_key,
                    match_value=match_value,
                ).single()

                if rel_record:
                    created_relationships.append(
                        f"{relationship_type} -> {target_label}({rel_record['target_value']})"
                    )

        relationship_summary = (
            ", ".join(created_relationships) if created_relationships else "no relationships added"
        )
        return (
            f"Upserted {node_label} node with key {node_record['node_key']!r}; "
            f"properties: {', '.join(property_keys)}; {relationship_summary}."
        )

    except Exception as e:
        return f"Error creating data node: {str(e)}"


# Hybrid search tools
from services.hybrid_search_service import HybridSearchService, SearchMethod, SearchResult

# Singleton service instance
_service: Optional[HybridSearchService] = None

def _get_service() -> HybridSearchService:
    global _service, sn_conn, neo4j_driver
    if _service is None:
        _service = HybridSearchService(sn_conn, neo4j_driver)
    return _service

def _format_results(results: List[SearchResult], analysis: dict) -> str:
    lines = ["## 🧠 Search Strategy"]
    lines.append(f"- **Recommended Method:** `{analysis['recommended_method']}`")
    lines.append(f"- **Confidence:** {analysis['confidence']:.0%}")
    lines.append(f"- **Reasoning:** _{analysis['reasoning']}_")
    lines.extend(["", "---", "", "## 📋 Results", ""])

    if not results:
        return "\n".join(lines) + "No specialists found for this criteria."

    for i, r in enumerate(results, 1):
        method_emoji = {
            SearchMethod.KEYWORD: "🔤",
            SearchMethod.RAG: "🧬",
            SearchMethod.HYBRID: "🔀",
        }.get(r.method, "•")

        lines.append(f"{i}. **{r.name}** ({r.score:.0%} match) {method_emoji}")
        lines.append(f"   👤 Role: {r.role}")
        if r.details.get("special"):
            lines.append(f"   🛠️ Specialty: {r.details['special']}")
        lines.append("")

    lines.extend(["---", "_Legend: 🔤 Keyword | 🧬 Semantic (RAG) | 🔀 Hybrid_"])
    return "\n".join(lines)

async def smart_search_tool(query: str, limit: int = 5) -> str:
    try:
        service = _get_service()
        response = service.smart_search(query, limit=limit)
        return _format_results(response["results"], response["analysis"].__dict__)
    except Exception as e:
        return f"Error in smart search: {str(e)}"

async def keyword_search(query: str, limit: int = 5) -> str:
    try:
        service = _get_service()
        analysis = service.analyze_query(query)
        results = service.keyword_search(analysis, limit=limit)
        return _format_results(results, analysis.__dict__)
    except Exception as e:
        return f"Error in keyword search: {str(e)}"

async def rag_search(query: str, limit: int = 5) -> str:
    try:
        service = _get_service()
        results = service.rag_search(query, limit=limit)
        analysis = {
            "recommended_method": SearchMethod.RAG,
            "confidence": 1.0,
            "reasoning": "Forced semantic retrieval tool invocation.",
        }
        return _format_results(results, analysis)
    except Exception as e:
        return f"Error in rag search: {str(e)}"

async def find_similar_survivors(name: str, limit: int = 3) -> str:
    try:
        service = _get_service()
        results = service.rag_search(f"Skills and roles similar to {name}", limit=limit)

        lines = [f"## 🧬 Survivors Similar to {name}", ""]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. **{r.name}** ({r.score:.2f} similarity)")
            lines.append(f"   Role: {r.role}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error finding similar survivors: {str(e)}"


# Survivor tools
async def get_survivors_with_skill(skill_name: str) -> str:
    try:
        if neo4j_driver is None:
            return "Neo4j driver not configured."
        with neo4j_driver.session() as session:
            result = session.run("""
                MATCH (s:Survivor)-[:HAS_SKILL]->(skill)
                WHERE skill.name CONTAINS $skill OR s.special CONTAINS $skill
                RETURN s.name AS survivor, skill.name AS skill_found
            """, skill=skill_name)

            data = result.data()
            if not data:
                return f"No survivors found with skill matching '{skill_name}'."

            formatted = [f"{r['survivor']} ({r['skill_found']})" for r in data]
            return f"Survivors with skill '{skill_name}': " + ", ".join(formatted)

    except Exception as e:
        return f"Error searching for skills: {str(e)}"

async def get_all_survivors() -> str:
    try:
        if neo4j_driver is None:
            return "Neo4j driver not configured."
        with neo4j_driver.session() as session:
            result = session.run("MATCH (s:Survivor) RETURN s.name AS name, s.role AS role")

            survivors = [f"{r['name']} (Role: {r['role']})" for r in result]
            if not survivors:
                return "No survivors found in the network."

            return "All Network Survivors:\n- " + "\n- ".join(survivors)
    except Exception as e:
        return f"Error listing survivors: {str(e)}"

async def get_urgent_needs() -> str:
    try:
        if neo4j_driver is None:
            return "Neo4j driver not configured."
        with neo4j_driver.session() as session:
            result = session.run("""
                MATCH (s:Survivor)-[:HAS_NEED]->(n)
                WHERE n.priority IN ['High', 'Critical']
                RETURN s.name AS name, n.description AS need
            """)

            needs = [f"{r['need']} (Affecting: {r['name']})" for r in result]
            if not needs:
                return "No urgent needs detected at this time."

            return "Urgent Needs Registry:\n- " + "\n- ".join(needs)
    except Exception as e:
        return f"Error fetching urgent needs: {str(e)}"


# Agent definition (from agent.py)
agent_tools = [
    get_all_survivors,
    get_urgent_needs,
    keyword_search,
    rag_search,
    smart_search_tool,
    find_similar_survivors,
    upsert_data_node_from_graph,
]

agent_instruction = """
You are a helpful AI assistant for the Survivor Network.
Your goal is to route user requests to the most efficient search tool.

## 🎯 DECISION GUIDE
1. EXACT LOOKUPS: Use 'get_all_survivors' for general lists.
2. DIRECT SEARCH: 
    - Use 'keyword_search' for specific roles/names (e.g., "Find Delivery Riders").
    - Use 'rag_search' for abstract problems (e.g., "Who can fix a leg?").
3. HYBRID SEARCH: Use 'smart_search_tool' ONLY for complex, multi-part queries.
4. GRAPH WRITES: Use 'upsert_data_node_from_graph' only when the user explicitly wants to create or enrich a node.

## OUTPUT FORMAT
Whenever possible, provide results in markdown format with clear sections and bullet points for readability.
Account for the score or confidence of results when relevant, especially for RAG-based outputs, to help users understand the relevance of the information provided.
"""

# Create FastAPI app
app = FastAPI(title="ADK Middleware Proverbs Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create combined agent and ADK endpoint
combined_instruction = ("""
When a user asks you to do anything regarding proverbs, you MUST use the set_proverbs tool.

Follow the proverbs rules and the Survivor Network decision guide. Be creative and helpful.
""" + "\n\n" + agent_instruction)

combined_tools = [set_proverbs, get_weather] + agent_tools

combined_agent = LlmAgent(
    name="CombinedAgent",
    model="gemini-2.5-flash",
    instruction=combined_instruction,
    tools=combined_tools,
    before_agent_callback=on_before_agent,
    before_model_callback=before_model_modifier,
    after_model_callback=simple_after_model_modifier,
)

adk_combined_agent = ADKAgent(
    adk_agent=combined_agent,
    user_id="demo_user",
    session_timeout_seconds=3600,
    use_in_memory_services=True,
)

# Add the ADK endpoint for the combined agent
add_adk_fastapi_endpoint(app, adk_combined_agent, path="/")


@app.get("/api/graph")
async def get_graph_data():
    """Retrieve survivor graph relationships for 3D visualization."""
    current_driver = get_neo4j_driver()
    if current_driver is None:
        return {
            "error": "Neo4j is not configured. Set NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD.",
            "nodes": [],
            "links": [],
        }

    with current_driver.session() as session:
        result = session.run(
            """
            MATCH (s:Survivor)-[r]->(t)
            RETURN s.name AS source,
                   type(r) AS rel_type,
                   t.name AS target,
                   s.role AS source_role,
                   properties(s) AS source_props,
                   labels(s) AS source_labels,
                   properties(t) AS target_props,
                   labels(t) AS target_labels
            """
        )

        nodes = {}
        links = []

        for record in result:
            source = record["source"]
            target = record["target"]

            if source not in nodes:
                source_props = (
                    dict(record.get("source_props", {}))
                    if record.get("source_props") is not None
                    else {}
                )
                filtered_source = {
                    key: value
                    for key, value in source_props.items()
                    if key in {"role", "secondaryRole", "special"}
                }
                nodes[source] = {
                    "id": source,
                    "group": record.get("source_role", "Common"),
                    "properties": filtered_source,
                    "labels": (
                        list(record.get("source_labels", []))
                        if record.get("source_labels") is not None
                        else []
                    ),
                }

            if target not in nodes:
                target_props = (
                    dict(record.get("target_props", {}))
                    if record.get("target_props") is not None
                    else {}
                )
                filtered_target = {
                    key: value
                    for key, value in target_props.items()
                    if key in {"role", "secondaryRole", "special"}
                }
                nodes[target] = {
                    "id": target,
                    "group": "Common",
                    "properties": filtered_target,
                    "labels": (
                        list(record.get("target_labels", []))
                        if record.get("target_labels") is not None
                        else []
                    ),
                }

            links.append(
                {
                    "source": source,
                    "target": target,
                    "label": record["rel_type"],
                }
            )

        return {"nodes": list(nodes.values()), "links": links}


@app.get("/api/node/{name}")
async def get_node_properties(name: str):
    """Retrieve properties and labels for a node identified by its name."""
    current_driver = get_neo4j_driver()
    if current_driver is None:
        return {
            "found": False,
            "name": name,
            "error": "Neo4j is not configured. Set NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD.",
        }

    with current_driver.session() as session:
        result = session.run(
            "MATCH (n) WHERE n.name = $name RETURN properties(n) AS props, labels(n) AS labels",
            name=name,
        )
        record = result.single()
        if not record:
            return {"found": False, "name": name}

        props = record.get("props", {})
        labels = record.get("labels", [])
        return {
            "found": True,
            "name": name,
            "properties": dict(props),
            "labels": labels,
        }


@app.on_event("shutdown")
def close_neo4j_driver():
    global driver
    if driver is not None:
        driver.close()
        driver = None

if __name__ == "__main__":
    import uvicorn

    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  Warning: GOOGLE_API_KEY environment variable not set!")
        print("   Set it with: export GOOGLE_API_KEY='your-key-here'")
        print("   Get a key from: https://makersuite.google.com/app/apikey")
        print()

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
