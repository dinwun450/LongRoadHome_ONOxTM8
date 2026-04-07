import os
import snowflake.connector
from neo4j import GraphDatabase

# 1. Setup Connections (read from environment variables)
sn_conn = snowflake.connector.connect(
    user=os.environ.get("SNOWFLAKE_USER"),
    password=os.environ.get("SNOWFLAKE_PASSWORD"),
    account=os.environ.get("SNOWFLAKE_ACCOUNT"),
    warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE"),
    database=os.environ.get("SNOWFLAKE_DATABASE"),
    schema=os.environ.get("SNOWFLAKE_SCHEMA"),
)
neo4j_uri = os.environ.get("NEO4J_URI")
neo4j_user = os.environ.get("NEO4J_USER")
neo4j_password = os.environ.get("NEO4J_PASSWORD")
neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

def setup_tokyo_survivors():
    # --- PART A: SNOWFLAKE (The Source of Truth) ---
    with sn_conn.cursor() as cur:
        cur.execute("CREATE OR REPLACE SCHEMA TOKYO_MAG_EIGHT_SCHEMA")
        cur.execute("USE SCHEMA TOKYO_MAG_EIGHT_SCHEMA")
        # Equivalent to the DDL_STATEMENTS in setup_data.py
        cur.execute("CREATE OR REPLACE TABLE survivors (id STRING, name STRING, role STRING, secondaryRole STRING, special STRING, status STRING)")
        
        # Seeding our Tokyo Magnitude characters + Jino's friends
        characters = [
            ('s1', 'Mirai Onozawa', 'Student', 'Navigator', "Older Sister of Yuuki", 'Active'),
            ('s2', 'Yuuki Onozawa', 'Student', 'Lookout', "Younger Brother of Mirai", 'Injured'),
            ('s3', 'Mari Kusakabe', 'Delivery Rider', 'First Responder', None, 'Active'),
            ('s4', 'Masami Onozawa', 'Parent', None, "Mother", 'Unknown'),
            ('s5', 'Seiji Onozawa', 'Parent', None, "Father", 'Unknown'),

            # Jino's Friends (just for more reference data in the graph)
            ('s6', 'Jino Onogawa', 'Student', 'Navigator', 'Snowflake SQUAD Member', 'Injured'),
            ('s7', 'Maruna Harupuami', 'Student', 'Lookout', None, 'Active'),
            ('s8', 'Victor Yugiu', 'Student', 'Assistant', 'Sprouters Club Executive', 'Active'),
            ('s9', 'Lyde Powell', 'Student', 'First Responder', 'Francophone', 'Active'),
            ('s10', 'Arushu Patel', 'Student', 'First Responder', None, 'Active'),
            ('s11', 'Kenny Fukami', 'Student', 'Navigator', None, 'Active'),
            ('s12', 'Molly-Ann Barbu', 'Student', 'Assistant', 'Francophone', 'Active')
        ]
        cur.executemany("INSERT INTO survivors VALUES (%s, %s, %s, %s, %s, %s)", characters)
        print("✅ Snowflake: Characters seeded.")

    # --- PART B: NEO4J (The Relationship Graph) ---
    with neo4j_driver.session() as session:
        # Equivalent to create_property_graph.py logic
        # We create the nodes and the connections (Edges)
        cypher_query = """
        MERGE (mirai:Survivor {id: 's1'}) SET mirai.name = 'Mirai Onozawa', mirai.role = 'Student', mirai.secondaryRole = 'Navigator', mirai.special = NULL, mirai.status = 'Active'
        MERGE (yuuki:Survivor {id: 's2'}) SET yuuki.name = 'Yuuki Onozawa', yuuki.role = 'Student', yuuki.secondaryRole = 'Lookout', yuuki.special = NULL, yuuki.status = 'Injured'
        MERGE (mari:Survivor {id: 's3'}) SET mari.name = 'Mari Kusakabe', mari.role = 'Delivery Rider', mari.secondaryRole = 'First Responder', mari.special = 'First Responder', mari.status = 'Active'
        MERGE (masami:Survivor {id: 's4'}) SET masami.name = 'Masami Onozawa', masami.role = 'Parent', masami.secondaryRole = 'Mother', masami.special = NULL, masami.status = 'Unknown'
        MERGE (seiji:Survivor {id: 's5'}) SET seiji.name = 'Seiji Onozawa', seiji.role = 'Parent', seiji.secondaryRole = 'Father', seiji.special = NULL, seiji.status = 'Unknown'
        MERGE (jino:Survivor {id: 's6'}) SET jino.name = 'Jino Onogawa', jino.role = 'Student', jino.secondaryRole = 'Navigator', jino.special = 'Snowflake SQUAD Member', jino.status = 'Injured'
        MERGE (maruna:Survivor {id: 's7'}) SET maruna.name = 'Maruna Harupuami', maruna.role = 'Student', maruna.secondaryRole = 'Lookout', maruna.special = NULL, maruna.status = 'Active'
        MERGE (victor:Survivor {id: 's8'}) SET victor.name = 'Victor Yugiu', victor.role = 'Student', victor.secondaryRole = 'Assistant', victor.special = 'Sprouters Club Executive', victor.status = 'Active'
        MERGE (lyde:Survivor {id: 's9'}) SET lyde.name = 'Lyde Powell', lyde.role = 'Student', lyde.secondaryRole = 'First Responder', lyde.special = 'Francophone', lyde.status = 'Active'
        MERGE (arushu:Survivor {id: 's10'}) SET arushu.name = 'Arushu Patel', arushu.role = 'Student', arushu.secondaryRole = 'First Responder', arushu.special = NULL, arushu.status = 'Active'
        MERGE (kenny:Survivor {id: 's11'}) SET kenny.name = 'Kenny Fukami', kenny.role = 'Student', kenny.secondaryRole = 'Navigator', kenny.special = NULL, kenny.status = 'Active'
        MERGE (mollyAnn:Survivor {id: 's12'}) SET mollyAnn.name = 'Molly-Ann Barbu', mollyAnn.role = 'Student', mollyAnn.secondaryRole = 'Assistant', mollyAnn.special = 'Francophone', mollyAnn.status = 'Active'

        // Define the relationships
        MERGE (mari)-[:PROTECTING]->(yuuki)
        MERGE (mari)-[:GUIDING]->(mirai)
        MERGE (mirai)-[:SIBLING_OF]->(yuuki)
        MERGE (yuuki)-[:SIBLING_OF]->(mirai)

        // Jino's friends!
        MERGE (jino)-[:FRIEND_OF]->(maruna)
        MERGE (jino)-[:FRIEND_OF]->(victor)
        MERGE (jino)-[:FRIEND_OF]->(lyde)
        MERGE (jino)-[:FRIEND_OF]->(arushu)
        MERGE (jino)-[:FRIEND_OF]->(kenny)
        MERGE (jino)-[:FRIEND_OF]->(mollyAnn)
        MERGE (lyde)-[:FRIEND_OF]->(mollyAnn)
        MERGE (arushu)-[:FRIEND_OF]->(kenny)
        MERGE (victor)-[:FRIEND_OF]->(maruna)

        // Jino and his friends guide or protect Mirai and Yuuki
        MERGE (jino)-[:GUIDING]->(mirai)
        MERGE (jino)-[:GUIDING]->(yuuki)

        // Lyde and Arushu are First Responders, so they PROTECT
        MERGE (lyde)-[:PROTECTING]->(yuuki)
        MERGE (arushu)-[:PROTECTING]->(yuuki)

        // The rest of Jino's friends GUIDE
        MERGE (maruna)-[:GUIDING]->(mirai)
        MERGE (maruna)-[:GUIDING]->(yuuki)
        MERGE (victor)-[:GUIDING]->(mirai)
        MERGE (victor)-[:GUIDING]->(yuuki)
        MERGE (kenny)-[:GUIDING]->(mirai)
        MERGE (kenny)-[:GUIDING]->(yuuki)
        MERGE (mollyAnn)-[:GUIDING]->(mirai)
        MERGE (mollyAnn)-[:GUIDING]->(yuuki)

        // Jino and his friends also ASSIST Mari in her delivery missions
        MERGE (jino)-[:ASSISTING]->(mari)
        MERGE (lyde)-[:ASSISTING]->(mari)
        MERGE (arushu)-[:ASSISTING]->(mari)
        MERGE (victor)-[:ASSISTING]->(mari)
        MERGE (kenny)-[:ASSISTING]->(mari)
        MERGE (mollyAnn)-[:ASSISTING]->(mari)
        MERGE (maruna)-[:ASSISTING]->(mari)

        // Now, the Onozawa's parents!
        MERGE (masami)-[:PARENT_OF]->(mirai)
        MERGE (masami)-[:PARENT_OF]->(yuuki)
        MERGE (seiji)-[:PARENT_OF]->(mirai)
        MERGE (seiji)-[:PARENT_OF]->(yuuki)
        """
        session.run(cypher_query)
        print("✅ Neo4j: Property Graph created and linked.")

if __name__ == "__main__":
    setup_tokyo_survivors()