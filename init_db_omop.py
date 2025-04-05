# %%
import sqlite3
import os
import pandas as pd

# %%
# Define paths
db_path = "db/omop_vocab.sqlite"
csv_dir = "vocabulary"  # This should contain the OMOP CDM vocabulary CSVs

# Create DB directory if it doesn't exist
os.makedirs(os.path.dirname(db_path), exist_ok=True)

# Connect to SQLite database
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Define table schemas for OMOP Vocabulary tables
schemas = {
    "concept": """
        CREATE TABLE IF NOT EXISTS concept (
            concept_id INTEGER PRIMARY KEY,
            concept_name TEXT NOT NULL,
            domain_id TEXT NOT NULL,
            vocabulary_id TEXT NOT NULL,
            concept_class_id TEXT NOT NULL,
            standard_concept TEXT,
            concept_code TEXT NOT NULL,
            valid_start_date TEXT NOT NULL,
            valid_end_date TEXT NOT NULL,
            invalid_reason TEXT
        )
    """,
    "concept_ancestor": """
        CREATE TABLE IF NOT EXISTS concept_ancestor (
            ancestor_concept_id INTEGER,
            descendant_concept_id INTEGER,
            min_levels_of_separation INTEGER,
            max_levels_of_separation INTEGER
        )
    """,
    "concept_class": """
        CREATE TABLE IF NOT EXISTS concept_class (
            concept_class_id TEXT PRIMARY KEY,
            concept_class_name TEXT NOT NULL,
            concept_class_concept_id INTEGER NOT NULL
        )
    """,
    "concept_relationship": """
        CREATE TABLE IF NOT EXISTS concept_relationship (
            concept_id_1 INTEGER,
            concept_id_2 INTEGER,
            relationship_id TEXT,
            valid_start_date TEXT,
            valid_end_date TEXT,
            invalid_reason TEXT
        )
    """,
    "domain": """
        CREATE TABLE IF NOT EXISTS domain (
            domain_id TEXT PRIMARY KEY,
            domain_name TEXT NOT NULL,
            domain_concept_id INTEGER NOT NULL
        )
    """,
    "vocabulary": """
        CREATE TABLE IF NOT EXISTS vocabulary (
            vocabulary_id TEXT PRIMARY KEY,
            vocabulary_name TEXT NOT NULL,
            vocabulary_reference TEXT,
            vocabulary_version TEXT,
            vocabulary_concept_id INTEGER NOT NULL
        )
    """,
    "relationship": """
        CREATE TABLE IF NOT EXISTS relationship (
            relationship_id TEXT PRIMARY KEY,
            relationship_name TEXT NOT NULL,
            is_hierarchical TEXT NOT NULL,
            defines_ancestry TEXT NOT NULL,
            reverse_relationship_id TEXT NOT NULL,
            relationship_concept_id INTEGER NOT NULL
        )
    """
}

# Create tables
for name, ddl in schemas.items():
    print(f"Creating table {name}...")
    cur.execute(ddl)

conn.commit()

# Load CSVs into tables
for table in schemas:
    csv_path = os.path.join(csv_dir, f"{table}.csv")
    if os.path.exists(csv_path):
        print(f"Loading {csv_path}...")
        df = pd.read_csv(csv_path, delimiter='\t', dtype=str).fillna('')
        df.to_sql(table, conn, if_exists="replace", index=False)
    else:
        print(f"⚠️ CSV for {table} not found at {csv_path}")

conn.close()
print("✅ OMOP Vocabulary SQLite DB created and populated.")

