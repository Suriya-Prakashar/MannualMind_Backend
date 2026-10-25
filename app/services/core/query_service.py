
from app.services.core.retrieval_service import retrieve_chunks


def process_query(query: str) -> dict:
    """Process a user query and retrieve matching manual chunks."""
    cleaned_query = query.strip()

    if not cleaned_query:
        raise ValueError("Query cannot be empty.")

    results = retrieve_chunks(cleaned_query)

    return {
        "query": cleaned_query,
        "message": (
            "Matching manual chunks retrieved."
            if results
            else "No matching manual chunks found."
        ),
        "status": "success",
        "results": results,
    }