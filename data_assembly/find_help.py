import snowflake.connector
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

sn_conn = snowflake.connector.connect(
            user=os.getenv("SNOWFLAKE_USER"),
            password=os.getenv("SNOWFLAKE_PASSWORD"),
            account=os.getenv("SNOWFLAKE_ACCOUNT"),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
            database=os.getenv("SNOWFLAKE_DATABASE"),
            schema=os.getenv("SNOWFLAKE_SCHEMA")
        )
neo4j_driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

def find_specialized_help(user_query):
    # 1. Convert user query to a vector using Snowflake Cortex
    with sn_conn.cursor() as cur:
        # Use the same model used for the table: snowflake-arctic-embed-m
        cur.execute("""
            SELECT SNOWFLAKE.CORTEX.EMBED_TEXT_768(
                'snowflake-arctic-embed-m', 
                %s
            )
        """, (user_query,))
        query_vector = cur.fetchone()[0]

    # 2. Search Neo4j using the Vector Index
    with neo4j_driver.session() as session:
        # Using the index you created: survivor_embeddings
        result = session.run("""
            CALL db.index.vector.queryNodes('survivor_embeddings', 1, $vector)
            YIELD node, score
            RETURN 
                node.name AS name, 
                node.role AS primary_role, 
                node.secondaryRole AS secondary_role, 
                node.special AS specialty, 
                score
        """, vector=query_vector)
        
        match = result.single()
        
        if match:
            print(f"🎯 Match Found: {match['name']} (Score: {match['score']:.4f})")
            print(f"   Role: {match['primary_role']} | Specialty: {match['specialty']}")
            return match
        else:
            print("❌ No matching specialist found in the network.")
            return None

# --- Example Usage ---
find_specialized_help("Who can assist anyone as a Snowflake SQUAD Member?")