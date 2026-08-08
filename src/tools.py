"""
Clinical Evidence Retrieval Tool

Provides grounded retrieval from clinical guideline documents stored in Qdrant.
Returns formatted chunks with source citations and similarity scores for LLM consumption.
"""
from langchain.tools import tool
from rag.retrieval import retrieve_chunks_with_scores
from langchain_core.documents import Document


@tool
def retrieve_clinical_evidence(query: str, k: int = 5) -> str:
    """
    Retrieve relevant clinical guideline chunks for a medical query.

    Args:
        query: The medical question or topic to search for.
        k: Number of top chunks to retrieve (default: 5).

    Returns:
        Formatted string with retrieved chunks, each tagged with source citation
        and similarity score. Returns a clear message if no results found.
    """
    if not query or not query.strip():
        return "Error: Empty query provided. Please provide a medical question or topic."

    try:
        results = retrieve_chunks_with_scores(query=query.strip(), k=k)
    except Exception as e:
        return f"Error during retrieval: {type(e).__name__}: {str(e)}"

    if not results:
        return (
            "No relevant clinical guidelines found for this query. "
            "Try rephrasing or using different medical terminology."
        )

    formatted_chunks = []
    for i, (doc, score) in enumerate(results, 1):
        source = doc.metadata.get("source", "unknown")
        # Truncate very long chunks to keep context manageable
        content = doc.page_content
        if len(content) > 2000:
            content = content[:2000] + "... [truncated]"

        formatted_chunks.append(
            f"[Source {i}: {source}, relevance: {score:.3f}]\n{content}"
        )

    header = f"Retrieved {len(formatted_chunks)} relevant chunk(s) for query: \"{query}\"\n"
    return header + "\n\n---\n\n".join(formatted_chunks)


# Export the tool for the agent graph
tools = [retrieve_clinical_evidence]