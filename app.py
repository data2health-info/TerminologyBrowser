import streamlit as st
import sqlite3
import json
import pandas as pd
from typing import List, Dict

# --- Config
DB_PATH = "db/omop_vocab.sqlite"
FHIR_SYSTEMS = {
    "SNOMED": "http://snomed.info/sct",
    "LOINC": "http://loinc.org",
    "RxNorm": "http://www.nlm.nih.gov/research/umls/rxnorm"
}

# --- DB Functions
def get_connection():
    return sqlite3.connect(DB_PATH)

def search_concepts(term: str, vocab: str = None, search_by: str = "string") -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    if search_by == "string":
        query = """
        SELECT concept_id, concept_name, vocabulary_id, concept_code
        FROM concept
        WHERE concept_name LIKE ?
        """
        params = [f"%{term}%"]
    else:  # search_by == "code"
        query = """
        SELECT concept_id, concept_name, vocabulary_id, concept_code
        FROM concept
        WHERE concept_code = ?
        """
        params = [term]
    if vocab:
        query += " AND vocabulary_id = ?"
        params.append(vocab)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "concept_id": r[0],
            "concept_name": r[1],
            "vocabulary_id": r[2],
            "concept_code": r[3]
        } for r in rows
    ]

def get_descendants(concepts: List[str], vocabulary_id: str = "SNOMED", search_by: str = "code") -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    if search_by == "string":
        concept_filter = " OR ".join(["p.concept_name LIKE ?" for _ in concepts])
        params = [f"%{c}%" for c in concepts]
    else:
        concept_filter = " OR ".join(["p.concept_code = ?" for _ in concepts])
        params = concepts

    query = f"""
    SELECT c.concept_name, c.vocabulary_id, c.concept_code
    FROM concept_ancestor ca
    JOIN concept c ON ca.descendant_concept_id = c.concept_id
    JOIN concept p ON ca.ancestor_concept_id = p.concept_id
    WHERE ({concept_filter})
    AND p.vocabulary_id = ?
    """
    params += [vocabulary_id]
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "concept_name": r[0],
            "vocabulary_id": r[1],
            "concept_code": r[2]
        } for r in rows
    ]

def generate_fhir_valueset(name: str, concepts: List[Dict]) -> Dict:
    includes = {}
    for c in concepts:
        system_url = FHIR_SYSTEMS.get(c["vocabulary_id"], "http://example.org")
        includes.setdefault(system_url, []).append({
            "code": c["concept_code"],
            "display": c["concept_name"]
        })

    fhir_valueset = {
        "resourceType": "ValueSet",
        "url": f"https://data2health.info/fhir/ValueSet/{name}",
        "name": name,
        "status": "active",
        "compose": {
            "include": [
                {
                    "system": system,
                    "concept": codes
                } for system, codes in includes.items()
            ]
        }
    }
    return fhir_valueset

# --- Streamlit UI
st.title("Terminology Code Search for AMRonFHIR Nepal")

search_term = st.text_input("Search Term")
vocab_filter = st.selectbox("Filter by Vocabulary", options=["", "SNOMED", "LOINC", "RxNorm"])
search_by = st.selectbox("Search By", options=["string", "code"])

if st.button("Search"):
    concepts = search_concepts(search_term, vocab_filter or None, search_by=search_by)
    st.write(f"Found {len(concepts)} concepts")

    if concepts:
        df_concepts = pd.DataFrame(concepts).drop(columns=["concept_id"])
        st.dataframe(df_concepts)
        csv = df_concepts.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download Concepts as CSV",
            csv,
            "concepts.csv",
            "text/csv",
            key='download-concepts-csv'
        )

        selected = df_concepts.to_dict(orient="records")
        vs_name = st.text_input("ValueSet Name")
        if vs_name:
            vs_data = generate_fhir_valueset(vs_name, selected)
            st.download_button("Download ValueSet JSON", json.dumps(vs_data, indent=2), file_name=f"{vs_name}.json")
            st.json(vs_data)
else:
    st.info("Enter a term to search concepts and click 'Search'.")

# --- Dynamic SNOMED Descendant Selector
st.subheader("Build from SNOMED Ancestors")

ancestor_search = st.text_input("Search SNOMED Concepts for Ancestors")
ancestor_search_by = st.selectbox("Search SNOMED Ancestors By", options=["string", "code"])

if st.button("Search SNOMED Ancestors"):
    snomed_concepts = search_concepts(ancestor_search, "SNOMED", search_by=ancestor_search_by)
    st.write(f"Found {len(snomed_concepts)} SNOMED concepts")

    selected_ancestors = []
    if snomed_concepts:
        df_snomed = pd.DataFrame(snomed_concepts).drop(columns=["concept_id"])
        st.dataframe(df_snomed)
        csv = df_snomed.to_csv(index=False).encode('utf-8')
        st.download_button("Download SNOMED Concepts as CSV", csv, "snomed_concepts.csv", "text/csv")
        selected_ancestors = [c["concept_code"] if ancestor_search_by == "code" else c["concept_name"] for c in snomed_concepts]

    if selected_ancestors and st.button("Get Descendants"):
        descendants = get_descendants(selected_ancestors, vocabulary_id="SNOMED", search_by=ancestor_search_by)
        st.write(f"Loaded {len(descendants)} descendant concepts")

        if descendants:
            df_descendants = pd.DataFrame(descendants)
            st.dataframe(df_descendants)
            csv = df_descendants.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download Descendants as CSV",
                csv,
                "descendants.csv",
                "text/csv",
                key='download-descendants-csv'
            )

            selected_descendants = descendants
            vs_name = st.text_input("ValueSet Name for SNOMED Descendants")
            if vs_name:
                vs_data = generate_fhir_valueset(vs_name, selected_descendants)
                st.download_button("Download Descendants ValueSet JSON", json.dumps(vs_data, indent=2), file_name=f"{vs_name}.json")
                st.json(vs_data)