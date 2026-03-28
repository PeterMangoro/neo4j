import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

from .paths import DOTENV_PATH


def _get_driver():
    load_dotenv(DOTENV_PATH)
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, user, password]):
        raise RuntimeError("Missing Neo4j credentials in .env (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD).")

    return GraphDatabase.driver(uri, auth=(user, password))


def setup_schema():
    driver = _get_driver()
    schema_queries = [
        "CREATE CONSTRAINT paper_id_unique IF NOT EXISTS FOR (p:Paper) REQUIRE p.paper_id IS UNIQUE",
        "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE",
        "CREATE CONSTRAINT gene_hgnc_unique IF NOT EXISTS FOR (g:Gene) REQUIRE g.hgnc_id IS UNIQUE",
        "CREATE CONSTRAINT author_key_unique IF NOT EXISTS FOR (a:Author) REQUIRE a.author_key IS UNIQUE",
        "CREATE CONSTRAINT entity_key_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_key IS UNIQUE",
        "CREATE CONSTRAINT claim_id_unique IF NOT EXISTS FOR (c:Claim) REQUIRE c.claim_id IS UNIQUE",
        "CREATE INDEX gene_symbol_idx IF NOT EXISTS FOR (g:Gene) ON (g.official_symbol)",
        "CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.type)",
        "CREATE INDEX paper_filename_idx IF NOT EXISTS FOR (p:Paper) ON (p.filename)",
        "CREATE INDEX paper_year_idx IF NOT EXISTS FOR (p:Paper) ON (p.year)",
        "CREATE INDEX paper_doi_idx IF NOT EXISTS FOR (p:Paper) ON (p.doi)",
        """CREATE VECTOR INDEX chunk_embedding_idx IF NOT EXISTS
           FOR (c:Chunk) ON (c.embedding)
           OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}}""",
    ]

    with driver.session() as session:
        for query in schema_queries:
            session.run(query)
            print(f"Ran: {query.splitlines()[0][:80]}...")

    driver.close()
    print("Schema created successfully!")


if __name__ == "__main__":
    setup_schema()
