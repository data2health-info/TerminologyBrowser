# app.py
import streamlit as st
import sqlite3
import json
import pandas as pd
from typing import List, Dict

# Import the fuzzy matching utility function
from utils.fuzzy_utils import apply_fuzzy_match

# --- Config
DB_PATH = "db/omop_vocab.sqlite" # Make sure this path is correct
FHIR_SYSTEMS = {
    "SNOMED": "http://snomed.info/sct",
    "LOINC": "http://loinc.org",
    "RxNorm": "http://www.nlm.nih.gov/research/umls/rxnorm"
}
DEFAULT_FUZZY_THRESHOLD = 80 # Define a default threshold

# --- DB Functions
def get_connection():
    # Consider adding error handling for connection
    try:
        return sqlite3.connect(DB_PATH)
    except sqlite3.Error as e:
        st.error(f"Database connection error: {e}. Please ensure '{DB_PATH}' exists and is accessible.")
        st.stop() # Stop execution if DB connection fails

# Modified search_concepts function to use fuzzy_utils
def search_concepts(
    term: str,
    vocab: str = None,
    search_by: str = "string",
    fuzzy: bool = False,        # Parameter to enable/disable fuzzy search
    threshold: int = DEFAULT_FUZZY_THRESHOLD # Parameter for similarity threshold
) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()

    # Keep the original SQL query logic
    if search_by == "string":
        # LIKE is still useful for an initial broad filter from the DB
        # Using LOWER() in SQL can improve performance if DB indexes support it,
        # but LIKE with %term% might not use indexes effectively anyway.
        # Sticking with Python-side lowercasing for simplicity here.
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

    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    except sqlite3.Error as e:
        st.error(f"Database query error: {e}")
        rows = [] # Return empty list on query error
    finally:
        conn.close()

    # Apply fuzzy matching using the imported function if enabled and searching by string
    if search_by == "string" and fuzzy:
        results = apply_fuzzy_match(term, rows, threshold)
    else:
        # Original logic if not fuzzy or not searching by string
        results = [
            {
                "concept_id": r[0],
                "concept_name": r[1],
                "vocabulary_id": r[2],
                "concept_code": r[3]
            } for r in rows if len(r) == 4 # Basic check for row structure
        ]

    return results


def get_descendants(concepts: List[str], vocabulary_id: str = "SNOMED", search_by: str = "code") -> List[Dict]:
    # This function remains unchanged as fuzzy logic applied only to the initial ancestor search
    conn = get_connection()
    cursor = conn.cursor()
    # Using parameters properly to avoid SQL injection risks
    placeholders = ', '.join('?' for _ in concepts) # Generate ?, ?, ...

    if search_by == "string":
        # Be cautious with LIKE here if names aren't unique identifiers
        concept_filter = f"p.concept_name IN ({placeholders})"
        params = concepts
    else: # code
        concept_filter = f"p.concept_code IN ({placeholders})"
        params = concepts

    query = f"""
    SELECT c.concept_name, c.vocabulary_id, c.concept_code
    FROM concept_ancestor ca
    JOIN concept c ON ca.descendant_concept_id = c.concept_id
    JOIN concept p ON ca.ancestor_concept_id = p.concept_id
    WHERE ({concept_filter})
    AND p.vocabulary_id = ?
    """
    params.append(vocabulary_id) # Add vocabulary_id to parameters

    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    except sqlite3.Error as e:
        st.error(f"Database query error while getting descendants: {e}")
        rows = []
    finally:
        conn.close()

    return [
        {
            "concept_name": r[0],
            "vocabulary_id": r[1],
            "concept_code": r[2]
        } for r in rows if len(r) == 3
    ]

def generate_fhir_valueset(name: str, concepts: List[Dict]) -> Dict:
    # This function remains unchanged
    includes = {}
    for c in concepts:
        system_url = FHIR_SYSTEMS.get(c["vocabulary_id"], f"http://example.org/unknown-vocab/{c.get('vocabulary_id', 'NONE')}") # Handle unknown vocabs
        code = c.get("concept_code", "UNKNOWN_CODE")
        display = c.get("concept_name", "Unknown Concept Name")
        # Ensure code and display are strings
        code_str = str(code) if code is not None else "NULL_CODE"
        display_str = str(display) if display is not None else "NULL_DISPLAY"

        # Group concepts by system URL
        if system_url not in includes:
            includes[system_url] = []
        includes[system_url].append({
            "code": code_str,
            "display": display_str
        })

    fhir_valueset = {
        "resourceType": "ValueSet",
        "url": f"https://data2health.info/fhir/ValueSet/{name.replace(' ', '_')}", # Sanitize name for URL
        "identifier": [{"system": "urn:ietf:rfc:3986", "value": f"urn:uuid:{hash(name + json.dumps(includes))}"}], # Example identifier
        "version": "1.0.0", # Add version
        "name": name.replace(' ', '_'), # Sanitize name
        "title": name,
        "status": "active",
        "experimental": True,
        "date": pd.Timestamp.now(tz='UTC').isoformat(), # Add generation date - Use current date based on guideline
        "publisher": "Generated by OMOP-FHIR Terminology Tool", # Add publisher info
        "description": f"ValueSet generated from OMOP concepts based on search/selection criteria.",
        "compose": {
            "include": [
                {
                    "system": system,
                    "concept": codes
                } for system, codes in includes.items()
            ]
        }
    }
    # Validate generated ValueSet structure (basic check)
    if not fhir_valueset.get("compose", {}).get("include"):
         st.warning(f"ValueSet '{name}' was generated with an empty 'compose.include' section. Check input concepts.")

    return fhir_valueset

# --- Streamlit UI ---
st.set_page_config(layout="wide")
st.title("Terminology Search & ValueSet Builder")
st.caption(f"Using OMOP Vocabulary from: `{DB_PATH}` | Current Time: {pd.Timestamp.now(tz='Nepal/Kathmandu').strftime('%Y-%m-%d %H:%M:%S %Z')}") # Use current time based on guideline


# --- Main Search Section ---
st.header("1. Search Concepts")
col1, col2, col3 = st.columns(3)
with col1:
    search_term = st.text_input("Search Term", key="main_search_term")
    search_by = st.selectbox("Search By", options=["string", "code"], index=0, key="main_search_by")
with col2:
    vocab_filter = st.selectbox("Filter by Vocabulary", options=["", "SNOMED", "LOINC", "RxNorm"], index=0, key="main_vocab")
    # Conditionally enable fuzzy checkbox based on search_by selection
    is_string_search = (search_by == "string")
    fuzzy_enabled = st.checkbox("Enable Fuzzy Search", value=False, key="main_fuzzy_check", disabled=not is_string_search, help="Uses fuzzy matching for 'string' searches. Results include a similarity score (0-100).")
with col3:
    # Conditionally enable slider based on fuzzy checkbox
    fuzzy_threshold = st.slider("Fuzzy Match Threshold (%)", min_value=50, max_value=100, value=DEFAULT_FUZZY_THRESHOLD, key="main_fuzzy_slider", disabled=not fuzzy_enabled, help="Minimum similarity score required for a fuzzy match.")


search_button_clicked = st.button("Search Concepts", key="main_search_button", type="primary")

if search_button_clicked:
    if search_term:
        # Pass fuzzy parameters only when relevant (string search AND checkbox ticked)
        perform_fuzzy = (search_by == 'string' and fuzzy_enabled)
        with st.spinner(f"Searching for '{search_term}'..." + (" (fuzzy)" if perform_fuzzy else "")):
            concepts = search_concepts(
                search_term,
                vocab_filter or None,
                search_by=search_by,
                fuzzy=perform_fuzzy,
                threshold=fuzzy_threshold
            )
        st.session_state['search_results'] = concepts # Store/overwrite results in session state
        st.rerun() # Rerun to display results below without needing another button press
    else:
        st.warning("Please enter a search term.")
        if 'search_results' in st.session_state:
            del st.session_state['search_results'] # Clear previous results if search term is empty

# Display search results if they exist in session state
if 'search_results' in st.session_state:
    concepts = st.session_state['search_results']
    st.success(f"Found {len(concepts)} concepts.") # Use success box for results summary

    if concepts:
        # Prepare DataFrame - handle potential 'score' column
        df_concepts = pd.DataFrame(concepts)
        # Explicitly drop internal ID if it's present and you don't want it shown
        if 'concept_id' in df_concepts.columns:
            df_concepts = df_concepts.drop(columns=["concept_id"])

        display_columns = list(df_concepts.columns)
        if 'score' in display_columns:
            # Ensure 'score' is the last column for better readability
            display_columns.remove('score')
            display_columns.append('score')
            df_concepts = df_concepts[display_columns]
            st.dataframe(df_concepts, use_container_width=True, height=300) 
        else:
            st.dataframe(df_concepts, use_container_width=True, height=300)
        csv = df_concepts.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download Concepts as CSV",
            csv,
            f"{search_term or 'concepts'}_results.csv", 
            "text/csv",
            key='download-concepts-csv'
        )

        # --- ValueSet Generation from Search Results ---
        st.subheader("Generate ValueSet from Search Results")
        vs_name_search = st.text_input("ValueSet Name (e.g., MyConditionCodes)", key="vs_name_search")
        if vs_name_search:
            vs_data = generate_fhir_valueset(vs_name_search, concepts)
            col_vs1, col_vs2 = st.columns(2)
            with col_vs1:
                st.download_button(
                    f"Download ValueSet '{vs_name_search}' as JSON",
                    json.dumps(vs_data, indent=2),
                    file_name=f"{vs_name_search}.json",
                    mime="application/json",
                    key='download-vs-search-json'
                    )
            with col_vs2:
                 if st.button("Clear Search Results", key="clear_search"):
                     del st.session_state['search_results']
                     st.rerun() # Rerun to update UI

            st.json(vs_data, expanded=False) # Keep JSON collapsed by default
    else:
        st.info("No concepts found matching your criteria.")


st.divider() 
# --- Build from SNOMED Ancestors Section ---
st.header("2. Build ValueSet from SNOMED CT Ancestors")
st.write("Find SNOMED concepts, then retrieve all their descendant concepts to build a ValueSet.")

col_anc1, col_anc2, col_anc3 = st.columns(3)
with col_anc1:
    ancestor_search = st.text_input("Search SNOMED Ancestor Term", key="anc_search_term")
    ancestor_search_by = st.selectbox("Search Ancestor By", options=["string", "code"], index=0, key="anc_search_by") 
with col_anc2:
    is_anc_string_search = (ancestor_search_by == "string")
    ancestor_fuzzy_enabled = st.checkbox("Enable Fuzzy Search", value=False, key="anc_fuzzy_check", disabled = not is_anc_string_search, help="Uses fuzzy matching for 'string' ancestor searches.")
with col_anc3:
    ancestor_fuzzy_threshold = st.slider("Ancestor Fuzzy Threshold (%)", min_value=50, max_value=100, value=DEFAULT_FUZZY_THRESHOLD, key="anc_fuzzy_slider", disabled=not ancestor_fuzzy_enabled, help="Minimum similarity score for fuzzy ancestor match.")


search_ancestors_clicked = st.button("Search SNOMED Ancestors", key="anc_search_button", type="primary")

if search_ancestors_clicked:
    if ancestor_search:
        # Pass fuzzy parameters only when relevant
        perform_fuzzy_anc = (ancestor_search_by == 'string' and ancestor_fuzzy_enabled)
        with st.spinner("Searching for ancestors..." + (" (fuzzy)" if perform_fuzzy_anc else "")):
            snomed_concepts = search_concepts(
                ancestor_search,
                "SNOMED", 
                search_by=ancestor_search_by,
                fuzzy=perform_fuzzy_anc,
                threshold=ancestor_fuzzy_threshold
                )
        # Store potential ancestors and search method in session state
        st.session_state['ancestor_candidates'] = snomed_concepts
        st.session_state['ancestor_search_by'] = ancestor_search_by # Need this for get_descendants
        # Clear any old descendant results when searching for new ancestors
        if 'descendant_results' in st.session_state:
            del st.session_state['descendant_results']
        st.rerun() # Rerun to display ancestor candidates
    else:
        st.warning("Please enter a term to search for SNOMED ancestors.")
        # Clear previous ancestor/descendant state if search term is empty
        if 'ancestor_candidates' in st.session_state: del st.session_state['ancestor_candidates']
        if 'descendant_results' in st.session_state: del st.session_state['descendant_results']
        if 'ancestor_search_by' in st.session_state: del st.session_state['ancestor_search_by']


# Display ancestor candidates if they exist
if 'ancestor_candidates' in st.session_state:
    snomed_concepts = st.session_state['ancestor_candidates']
    ancestor_search_method = st.session_state['ancestor_search_by']
    st.success(f"Found {len(snomed_concepts)} potential SNOMED ancestor concepts.")

    if snomed_concepts:
        df_snomed = pd.DataFrame(snomed_concepts)
        if 'concept_id' in df_snomed.columns:
             df_snomed = df_snomed.drop(columns=["concept_id"])

        display_columns_anc = list(df_snomed.columns)
        if 'score' in display_columns_anc:
             display_columns_anc.remove('score')
             display_columns_anc.append('score')
             df_snomed = df_snomed[display_columns_anc]
             st.dataframe(df_snomed, use_container_width=True, height=200)
        else:
            st.dataframe(df_snomed, use_container_width=True, height=200) 


        csv_anc = df_snomed.to_csv(index=False).encode('utf-8')
        st.download_button("Download Potential Ancestors as CSV", csv_anc, f"{ancestor_search or 'snomed'}_ancestors.csv", "text/csv", key='download-ancestors-csv')

        # --- Get Descendants Section ---
        st.subheader("Get Descendants for Found Ancestors")

        # Extract the correct identifier (code or name) based on how they were searched
        if ancestor_search_method == "code":
            selected_ancestor_identifiers = [c.get("concept_code") for c in snomed_concepts if c.get("concept_code")]
            if selected_ancestor_identifiers:
                 st.caption(f"Will fetch descendants for {len(selected_ancestor_identifiers)} SNOMED codes (preview): {', '.join(map(str,selected_ancestor_identifiers[:10]))}{'...' if len(selected_ancestor_identifiers) > 10 else ''}")
            else:
                 st.warning("No valid concept codes found in the potential ancestors.")
        else: # string search
            selected_ancestor_identifiers = [c.get("concept_name") for c in snomed_concepts if c.get("concept_name")]
            if selected_ancestor_identifiers:
                # Using concept_name for descendants might be less reliable, consider warning user
                st.caption(f"Will fetch descendants for {len(selected_ancestor_identifiers)} SNOMED concepts based on name (preview): {'; '.join(map(str, selected_ancestor_identifiers[:5]))}{'...' if len(selected_ancestor_identifiers) > 5 else ''}")
                st.warning("Note: Fetching descendants by concept name might be less precise than using concept codes if names are not unique.")
            else:
                 st.warning("No valid concept names found in the potential ancestors.")

        if selected_ancestor_identifiers and st.button("Get Descendants", key="get_desc_button", type="primary"):
            with st.spinner("Loading descendants... This might take a while."):
                 descendants = get_descendants(
                    selected_ancestor_identifiers,
                    vocabulary_id="SNOMED",
                    search_by=ancestor_search_method
                    )
            st.session_state['descendant_results'] = descendants # Store descendants
            st.rerun() # Rerun to display descendants
    else:
        st.info("No potential ancestor concepts found for your search.")


# Display descendants and allow ValueSet generation if they exist
if 'descendant_results' in st.session_state:
    descendants_data = st.session_state['descendant_results']
    st.subheader("Descendant Concepts")
    st.success(f"Loaded {len(descendants_data)} descendant concepts.")

    if descendants_data:
        df_descendants = pd.DataFrame(descendants_data)
        st.dataframe(df_descendants, use_container_width=True, height=300) 

        csv_desc = df_descendants.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download Descendants as CSV",
            csv_desc,
            f"{ancestor_search or 'snomed'}_descendants.csv",
            "text/csv",
            key='download-descendants-csv'
            )

        # --- ValueSet Generation for Descendants ---
        vs_name_desc = st.text_input("ValueSet Name for SNOMED Descendants", key="vs_name_desc")
        if vs_name_desc:
            vs_data_desc = generate_fhir_valueset(vs_name_desc, descendants_data)
            col_vs_desc1, col_vs_desc2 = st.columns(2)
            with col_vs_desc1:
                st.download_button(
                    f"Download Descendants ValueSet '{vs_name_desc}' as JSON",
                    json.dumps(vs_data_desc, indent=2),
                    file_name=f"{vs_name_desc}.json",
                    mime="application/json",
                    key='download-vs-desc-json'
                )
            with col_vs_desc2:
                 # Button to clear entire ancestor/descendant workflow state
                 if st.button("Clear Ancestor Search & Results", key="clear_desc"):
                     keys_to_clear = ['ancestor_candidates', 'descendant_results', 'ancestor_search_by']
                     for key in keys_to_clear:
                         if key in st.session_state:
                             del st.session_state[key]
                     st.rerun()

            st.json(vs_data_desc, expanded=False) # Keep JSON collapsed
    else:
        st.info("No descendant concepts were found for the selected ancestor(s).")


# --- Footer/Info ---
st.divider()
st.markdown("---")
st.caption(f"data2health.info | To facilitate AMRonFHIR implementation for Vendors") # 