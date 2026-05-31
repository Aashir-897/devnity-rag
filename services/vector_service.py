"""Qdrant vector DB — multi-tenant chunk storage and retrieval.
Falls back to ChromaDB if Qdrant is not available."""
import json
import re
import uuid
from rank_bm25 import BM25Okapi
from config import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION, TOP_K_CHUNKS, \
    CHROMA_DB_PATH, CHROMA_COLLECTION, BM25_WEIGHT, VECTOR_WEIGHT, RERANK_TOP_K, FINAL_TOP_K
from services.embeddings import get_embedding_model, _extract_page_lines

# ── BM25 Sparse Indexes (shared by Qdrant + ChromaDB branches) ──

_bm25_indexes: dict[str, BM25Okapi] = {}
_bm25_docs: dict[str, list[str]] = {}


def _tokenize(text: str) -> list[str]:
    return re.findall(r'\w+', text.lower())


def _build_bm25(pdf_id: str, chunks: list[str]):
    _bm25_indexes[pdf_id] = BM25Okapi([_tokenize(c) for c in chunks])
    _bm25_docs[pdf_id] = chunks


def _clear_bm25(pdf_id: str):
    _bm25_indexes.pop(pdf_id, None)
    _bm25_docs.pop(pdf_id, None)


def _bm25_search(query: str, pdf_id: str, top_k: int) -> list[dict]:
    if pdf_id not in _bm25_indexes:
        return []
    scores = _bm25_indexes[pdf_id].get_scores(_tokenize(query))
    indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    results = []
    for i in indices:
        if scores[i] <= 0:
            continue
        if len(results) >= top_k:
            break
        results.append({
            "text": _bm25_docs[pdf_id][i],
            "pages": [],
            "lines": [],
            "chunk_index": i,
            "score": float(scores[i]),
            "source": "bm25",
        })
    return results


def _rrf_merge(vector_results: list[dict], bm25_results: list[dict], top_k: int) -> list[dict]:
    k = 60
    score_map: dict[int, float] = {}
    item_map: dict[int, dict] = {}

    for rank, r in enumerate(vector_results):
        tid = r.get("chunk_index", id(r))
        item_map[tid] = r
        score_map[tid] = score_map.get(tid, 0) + VECTOR_WEIGHT / (k + rank + 1)

    for rank, r in enumerate(bm25_results):
        tid = r.get("chunk_index", id(r))
        if tid not in item_map:
            item_map[tid] = r
        score_map[tid] = score_map.get(tid, 0) + BM25_WEIGHT / (k + rank + 1)

    sorted_items = sorted(score_map.items(), key=lambda x: -x[1])
    out = []
    for tid, _ in sorted_items[:top_k]:
        item = dict(item_map[tid])
        item["score"] = score_map[tid]
        item.pop("source", None)
        out.append(item)
    return out


_reranker = None

def _get_reranker():
    global _reranker
    if _reranker is None:
        from services.reranker import rerank as _rr
        _reranker = _rr
    return _reranker


# ── Qdrant vs ChromaDB ──────────────────────────────────

_HAS_QDRANT = False

try:
    import qdrant_client
    from qdrant_client.http import models as qdrant_models

    _test_client = qdrant_client.QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
    _test_client.get_collections()
    _HAS_QDRANT = True
except Exception:
    _HAS_QDRANT = False

if _HAS_QDRANT:
    print("Qdrant connected — using Qdrant vector DB")

    def get_client():
        return qdrant_client.QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None, timeout=30)

    def _ensure_collection(client):
        if not client.collection_exists(QDRANT_COLLECTION):
            client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=qdrant_models.VectorParams(size=768, distance=qdrant_models.Distance.COSINE),
            )
        for field, ftype in [("pdf_id", qdrant_models.PayloadSchemaType.KEYWORD),
                               ("user_id", qdrant_models.PayloadSchemaType.INTEGER)]:
            try:
                client.create_payload_index(
                    collection_name=QDRANT_COLLECTION,
                    field_name=field,
                    field_type=ftype,
                )
            except Exception as e:
                print(f"Index error for {field}: {e}")

    def store_chunks(chunks, pdf_id, user_id=""):
        if not chunks:
            return 0
        model = get_embedding_model()
        client = get_client()
        _ensure_collection(client)

        must = [qdrant_models.FieldCondition(key="pdf_id", match=qdrant_models.MatchValue(value=pdf_id))]
        if user_id:
            must.append(qdrant_models.FieldCondition(key="user_id", match=qdrant_models.MatchValue(value=user_id)))
        client.delete(collection_name=QDRANT_COLLECTION, points_selector=qdrant_models.Filter(must=must), wait=True)

        embeddings = model.encode(chunks, show_progress_bar=True).tolist()
        points = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            info = _extract_page_lines(chunk)
            points.append(qdrant_models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{user_id}_{pdf_id}_{i}")), vector=emb,
                payload={"user_id": user_id, "pdf_id": pdf_id, "chunk_index": i, "text": chunk,
                         "pages": info["pages"], "lines": info["lines"]},
            ))
        client.upsert(collection_name=QDRANT_COLLECTION, points=points, wait=True)
        _build_bm25(pdf_id, chunks)
        print(f"Stored {len(chunks)} chunks in Qdrant for pdf_id: {pdf_id}")
        return len(chunks)

    def retrieve_chunks(query, pdf_id, user_id="", top_k=0):
        if top_k < 1:
            top_k = FINAL_TOP_K
        model = get_embedding_model()
        query_vec = model.encode([query])[0].tolist()
        client = get_client()
        _ensure_collection(client)
        must = [qdrant_models.FieldCondition(key="pdf_id", match=qdrant_models.MatchValue(value=pdf_id))]
        if user_id:
            must.append(qdrant_models.FieldCondition(key="user_id", match=qdrant_models.MatchValue(value=user_id)))
        try:
            results = client.search(
                collection_name=QDRANT_COLLECTION, query_vector=query_vec, limit=RERANK_TOP_K,
                query_filter=qdrant_models.Filter(must=must),
            )
        except Exception as e:
            print(f"Qdrant search timed out, falling back to BM25 only: {e}")
            combined = _bm25_search(query, pdf_id, top_k=RERANK_TOP_K)
            return combined[:top_k]
        vector_results = [{"text": r.payload.get("text", ""), "pages": r.payload.get("pages", []),
                           "lines": r.payload.get("lines", []), "chunk_index": r.payload.get("chunk_index", 0),
                           "score": r.score, "source": "vector"}
                          for r in results]

        bm25_results = _bm25_search(query, pdf_id, top_k=RERANK_TOP_K)
        combined = _rrf_merge(vector_results, bm25_results, top_k=RERANK_TOP_K)

        if len(combined) > 1:
            rerank_fn = _get_reranker()
            combined = rerank_fn(query, combined)

        return combined[:top_k]

    def delete_pdf_chunks(pdf_id, user_id=""):
        _clear_bm25(pdf_id)
        client = get_client()
        _ensure_collection(client)
        must = [qdrant_models.FieldCondition(key="pdf_id", match=qdrant_models.MatchValue(value=pdf_id))]
        if user_id:
            must.append(qdrant_models.FieldCondition(key="user_id", match=qdrant_models.MatchValue(value=user_id)))
        client.delete(collection_name=QDRANT_COLLECTION, points_selector=qdrant_models.Filter(must=must), wait=True)
        print(f"Deleted Qdrant chunks for pdf_id: {pdf_id}")

else:
    print("Qdrant not available — falling back to ChromaDB")
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    _chroma_client = None
    _collection = None

    def _get_chroma_collection():
        global _chroma_client, _collection
        if _collection is None:
            _chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH, settings=ChromaSettings(anonymized_telemetry=False))
            _collection = _chroma_client.get_or_create_collection(name=CHROMA_COLLECTION, metadata={"hnsw:space": "cosine"})
        return _collection

    def store_chunks(chunks, pdf_id, user_id=""):
        if not chunks:
            return 0
        model = get_embedding_model()
        collection = _get_chroma_collection()
        try:
            existing = collection.get(where={"pdf_id": pdf_id})
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
        except Exception:
            pass
        embeddings = model.encode(chunks, show_progress_bar=True).tolist()
        ids = [f"{pdf_id}_{i}" for i in range(len(chunks))]
        metadatas = []
        for i, chunk in enumerate(chunks):
            info = _extract_page_lines(chunk)
            metadatas.append({"pdf_id": pdf_id, "chunk_index": i, "user_id": user_id,
                              "pages": ",".join(str(p) for p in info["pages"]),
                              "lines": json.dumps(info["lines"])})
        collection.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)
        _build_bm25(pdf_id, chunks)
        print(f"Stored {len(chunks)} chunks in ChromaDB for pdf_id: {pdf_id}")
        return len(chunks)

    def retrieve_chunks(query, pdf_id, user_id="", top_k=0):
        if top_k < 1:
            top_k = FINAL_TOP_K
        model = get_embedding_model()
        query_embedding = model.encode([query])[0].tolist()
        collection = _get_chroma_collection()
        results = collection.query(query_embeddings=[query_embedding], n_results=RERANK_TOP_K, where={"pdf_id": pdf_id})
        vector_results = []
        if results and results["documents"]:
            metadatas = results["metadatas"][0] if results.get("metadatas") else []
            for i, doc in enumerate(results["documents"][0]):
                meta = metadatas[i] if i < len(metadatas) else {}
                pages_str = meta.get("pages", "")
                lines_str = meta.get("lines", "[]")
                vector_results.append({
                    "text": doc,
                    "pages": [int(p) for p in pages_str.split(",") if p.strip().isdigit()] if pages_str else [],
                    "lines": json.loads(lines_str) if isinstance(lines_str, str) else lines_str,
                    "chunk_index": int(meta.get("chunk_index", 0)),
                    "score": 1.0 - (i / len(results["documents"][0])),
                    "source": "vector",
                })

        bm25_results = _bm25_search(query, pdf_id, top_k=RERANK_TOP_K)
        combined = _rrf_merge(vector_results, bm25_results, top_k=RERANK_TOP_K)

        if len(combined) > 1:
            rerank_fn = _get_reranker()
            combined = rerank_fn(query, combined)

        return combined[:top_k]

    def delete_pdf_chunks(pdf_id, user_id=""):
        _clear_bm25(pdf_id)
        collection = _get_chroma_collection()
        try:
            existing = collection.get(where={"pdf_id": pdf_id})
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
                print(f"Deleted ChromaDB chunks for pdf_id: {pdf_id}")
        except Exception as e:
            print(f"Delete error: {e}")
