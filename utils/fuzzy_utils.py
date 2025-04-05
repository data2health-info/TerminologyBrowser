# fuzzy_utils.py
from typing import List, Dict, Tuple
from thefuzz import fuzz

# Define the indices based on the SELECT statement in app.py's search_concepts
# SELECT concept_id, concept_name, vocabulary_id, concept_code
CONCEPT_ID_IDX = 0
CONCEPT_NAME_IDX = 1
VOCABULARY_ID_IDX = 2
CONCEPT_CODE_IDX = 3

def apply_fuzzy_match(
    search_term: str,
    rows: List[Tuple],
    threshold: int,
) -> List[Dict]:
    """
    Applies fuzzy matching to a list of concept rows fetched from the database.

    Args:
        search_term: The term to match against.
        rows: A list of tuples, where each tuple represents a row from the
              concept table (concept_id, concept_name, vocabulary_id, concept_code).
        threshold: The minimum similarity score (0-100) required for a match.

    Returns:
        A list of dictionaries for concepts that meet the threshold,
        including a 'score' key, sorted by score descending.
    """
    scored_results = []
    term_lower = search_term.lower() # Lowercase search term once for efficiency

    for r in rows:
        # Ensure row has enough elements before accessing indices
        if len(r) > max(CONCEPT_ID_IDX, CONCEPT_NAME_IDX, VOCABULARY_ID_IDX, CONCEPT_CODE_IDX):
            concept_name = r[CONCEPT_NAME_IDX]
            if concept_name: # Ensure concept_name is not None
                # Calculate fuzzy score (partial_ratio is often good for finding terms within longer names)
                score = fuzz.partial_ratio(term_lower, concept_name.lower())
                if score >= threshold:
                    scored_results.append({
                        "concept_id": r[CONCEPT_ID_IDX],
                        "concept_name": concept_name,
                        "vocabulary_id": r[VOCABULARY_ID_IDX],
                        "concept_code": r[CONCEPT_CODE_IDX],
                        "score": score  # Add the score to the result
                    })
            else:
                # Handle cases where concept_name might be NULL/None in the DB if necessary
                pass
        else:
             # Handle potentially malformed rows if necessary
             pass

    # Sort results by score descending
    return sorted(scored_results, key=lambda x: x["score"], reverse=True)