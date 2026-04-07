import os
import snowflake.connector
from neo4j import GraphDatabase

# Snowflake connection using environment variables
sn_conn = snowflake.connector.connect(
    user=os.environ.get("SNOWFLAKE_USER"),
    password=os.environ.get("SNOWFLAKE_PASSWORD"),
    account=os.environ.get("SNOWFLAKE_ACCOUNT"),
    warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE"),
    database=os.environ.get("SNOWFLAKE_DATABASE"),
    schema=os.environ.get("SNOWFLAKE_SCHEMA"),
)

# Neo4j driver using environment variables
neo4j_uri = os.environ.get("NEO4J_URI")
neo4j_user = os.environ.get("NEO4J_USER")
neo4j_password = os.environ.get("NEO4J_PASSWORD")
neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

def sync_embeddings_to_graph():
    # --- Step A: Pull from Snowflake ---
    print("🛰️ Connecting to Snowflake...")
    
    with sn_conn.cursor() as cur:
        # Fetching names and the embeddings we just generated in Snowflake
        cur.execute("SELECT NAME, DESCRIPTION_EMBEDDING FROM SURVIVORS")
        survivor_data = cur.fetchall()
    
    # --- Step B: Push to Neo4j ---
    print(f"🧬 Syncing {len(survivor_data)} characters to Neo4j...")
    with neo4j_driver.session() as session:
        for name, embedding in survivor_data:
            # We use name as the key to match your existing graph nodes
            session.run("""
                MATCH (s:Survivor {name: $name})
                SET s.embedding = $vector
            """, name=name, vector=embedding)
            
    print("✅ Sync Complete. Jino and the team are now AI-searchable.")
    neo4j_driver.close()
    sn_conn.close()

if __name__ == "__main__":
    sync_embeddings_to_graph()