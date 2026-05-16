"""Sentence-transformers embeddings + ChromaDB storage/retrieval."""
import chromadb
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
from config import (
    EMBEDDING_MODEL, CHROMA_DB_PATH, CHROMA_COLLECTION,
    CHUNK_SIZE, CHUNK_OVERLAP
)


# ── Lazy Initialization ───────────────────────────────────────────────────────

_embedding_model = None
_chroma_client   = None
_collection      = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        print("Loading embedding model...")
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        print("Embedding model loaded")
    return _embedding_model


def get_collection():
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        _collection    = _chroma_client.get_or_create_collection(
            name=CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"}
        )
    return _collection


# ── Text Chunking ─────────────────────────────────────────────────────────────

def chunk_text(text: str) -> list[str]:
    """Split text into chunks for embedding."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = splitter.split_text(text)
    return [c.strip() for c in chunks if len(c.strip()) > 50]


# ── Store ─────────────────────────────────────────────────────────────────────

def store_chunks(chunks: list[str], pdf_id: str, metadata_base: dict = None):
    """Embed chunks and store them in ChromaDB."""
    if not chunks:
        return 0

    model      = get_embedding_model()
    collection = get_collection()

    try:
        existing = collection.get(where={"pdf_id": pdf_id})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass

    # Batch embed
    embeddings = model.encode(chunks, show_progress_bar=True).tolist()

    ids       = [f"{pdf_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = []

    for i, chunk in enumerate(chunks):
        meta = {"pdf_id": pdf_id, "chunk_index": i}
        if metadata_base:
            meta.update(metadata_base)
        metadatas.append(meta)

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas
    )

    print(f"Stored {len(chunks)} chunks for pdf_id: {pdf_id}")
    return len(chunks)


# ── Retrieve ──────────────────────────────────────────────────────────────────

def retrieve_chunks(query: str, pdf_id: str, top_k: int = 5) -> list[str]:
    """Retrieve the most relevant chunks for a query."""
    model      = get_embedding_model()
    collection = get_collection()

    query_embedding = model.encode([query])[0].tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"pdf_id": pdf_id}
    )

    if results and results["documents"]:
        return results["documents"][0]
    return []


# ── Delete ────────────────────────────────────────────────────────────────────

def delete_pdf_chunks(pdf_id: str):
    """Delete all chunks for a given PDF."""
    collection = get_collection()
    try:
        existing = collection.get(where={"pdf_id": pdf_id})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
            print(f"Deleted {len(existing['ids'])} chunks for {pdf_id}")
    except Exception as e:
        print(f"Delete error: {e}")
