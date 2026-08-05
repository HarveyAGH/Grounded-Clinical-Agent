"""
Retrieval step: query -> most relevant chunks.
v0 scope: plain similarity search. No reranking or query expansion yet
(deferred).
"""
from langchain_core.documents import Document

from .vectorstore import load_vectorstore

# Loaded once and reused, not reopened on every call -- important once this
# is invoked repeatedly inside an agent loop.
_store = None


def _get_store():
    global _store
    if _store is None:
        _store = load_vectorstore()
    return _store


def retrieve_chunks(query: str, k: int = 3) -> list[Document]:
    """Embeds the query with the same model used at ingestion time, and
    returns the k closest chunks by similarity.
    """
    return _get_store().similarity_search(query=query, k=k)


def retrieve_chunks_with_scores(query: str, k: int = 3) -> list[tuple[Document, float]]:
    """Same as retrieve_chunks, but also returns each chunk's similarity
    score -- useful when the caller (e.g. an agent) needs to judge confidence
    rather than blindly trusting the top-k.
    """
    return _get_store().similarity_search_with_score(query=query, k=k)


if __name__ == "__main__":
    test_query = "What is the main contribution of this paper?"
    results = retrieve_chunks(test_query)
    print(f"Query: {test_query}\n")
    for i, doc in enumerate(results, start=1):
        print(f"--- result {i} (source: {doc.metadata.get('source')}) ---")
        print(doc.page_content[:300])
        print()