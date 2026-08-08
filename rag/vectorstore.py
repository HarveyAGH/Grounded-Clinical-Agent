"""
Embedding + storage step: chunks -> persisted vector store.
v0 scope: single dense embedding model, local persisted Qdrant.
No hybrid (sparse) vectors yet (deferred).
"""
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore

QDRANT_PATH = "./data/qdrant_db"
COLLECTION_NAME = "clinical_guidelines"

# One embedding model instance, reused by both build and load.
embedding_model = HuggingFaceEmbeddings(model_name="abhinand/MedEmbed-small-v0.1")


def build_vectorstore(chunks: list[Document]) -> QdrantVectorStore:
    """Ingestion path: embed already-chunked Documents into a NEW, persisted
    Qdrant collection on disk. Run this once per corpus update, not on every
    startup -- it re-embeds everything each time it's called.
    """
    return QdrantVectorStore.from_documents(
        documents=chunks,
        embedding=embedding_model,
        path=QDRANT_PATH,
        collection_name=COLLECTION_NAME,
    )


def load_vectorstore() -> QdrantVectorStore:
    """Usage path: connect to an already-populated Qdrant collection
    without re-ingesting anything. This is what tools.py should call --
    it should never rebuild the index on every tool invocation.
    """
    return QdrantVectorStore.from_existing_collection(
        embedding=embedding_model,
        path=QDRANT_PATH,
        collection_name=COLLECTION_NAME,
    )
    
    
    
