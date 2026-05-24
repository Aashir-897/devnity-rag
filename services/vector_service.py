"""Qdrant vector DB — multi-tenant chunk storage and retrieval.
Falls back to ChromaDB if Qdrant is not available."""
import json
import uuid
from config import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION, TOP_K_CHUNKS, CHROMA_DB_PATH, CHROMA_COLLECTION
from services.embeddings import get_embedding_model, _extract_page_lines

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
        return qdrant_client.QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)

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
        print(f"Stored {len(chunks)} chunks in Qdrant for pdf_id: {pdf_id}")
        return len(chunks)

    def retrieve_chunks(query, pdf_id, user_id="", top_k=0):
        if top_k < 1:
            top_k = TOP_K_CHUNKS
        model = get_embedding_model()
        query_vec = model.encode([query])[0].tolist()
        client = get_client()
        _ensure_collection(client)
        must = [qdrant_models.FieldCondition(key="pdf_id", match=qdrant_models.MatchValue(value=pdf_id))]
        if user_id:
            must.append(qdrant_models.FieldCondition(key="user_id", match=qdrant_models.MatchValue(value=user_id)))
        results = client.search(
            collection_name=QDRANT_COLLECTION, query_vector=query_vec, limit=top_k,
            query_filter=qdrant_models.Filter(must=must),
        )
        return [{"text": r.payload.get("text", ""), "pages": r.payload.get("pages", []),
                 "lines": r.payload.get("lines", []), "chunk_index": r.payload.get("chunk_index", 0), "score": r.score}
                for r in results]

    def delete_pdf_chunks(pdf_id, user_id=""):
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
        print(f"Stored {len(chunks)} chunks in ChromaDB for pdf_id: {pdf_id}")
        return len(chunks)

    def retrieve_chunks(query, pdf_id, user_id="", top_k=0):
        if top_k < 1:
            top_k = TOP_K_CHUNKS
        model = get_embedding_model()
        query_embedding = model.encode([query])[0].tolist()
        collection = _get_chroma_collection()
        results = collection.query(query_embeddings=[query_embedding], n_results=top_k, where={"pdf_id": pdf_id})
        if not results or not results["documents"]:
            return []
        items = []
        metadatas = results["metadatas"][0] if results.get("metadatas") else []
        for i, doc in enumerate(results["documents"][0]):
            meta = metadatas[i] if i < len(metadatas) else {}
            pages_str = meta.get("pages", "")
            lines_str = meta.get("lines", "[]")
            items.append({
                "text": doc,
                "pages": [int(p) for p in pages_str.split(",") if p.strip().isdigit()] if pages_str else [],
                "lines": json.loads(lines_str) if isinstance(lines_str, str) else lines_str,
                "chunk_index": int(meta.get("chunk_index", 0)),
            })
        return items

    def delete_pdf_chunks(pdf_id, user_id=""):
        collection = _get_chroma_collection()
        try:
            existing = collection.get(where={"pdf_id": pdf_id})
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
                print(f"Deleted ChromaDB chunks for pdf_id: {pdf_id}")
        except Exception as e:
            print(f"Delete error: {e}")
