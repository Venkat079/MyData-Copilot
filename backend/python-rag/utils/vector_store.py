# python-rag/utils/vector_store.py
import os
import threading
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any

logger = logging.getLogger(__name__)

# Try langchain_community first, fallback to langchain
try:
    from langchain_community.vectorstores.faiss import FAISS as LC_FAISS  # type: ignore
    from langchain.schema import Document
    LC_MODULE = "langchain_community"
except Exception:
    try:
        from langchain.vectorstores import FAISS as LC_FAISS
        from langchain.schema import Document
        LC_MODULE = "langchain"
    except Exception as e:
        logger.exception("Failed to import FAISS from langchain or langchain_community: %s", e)
        raise

# embedding adapter using your utils.embeddings
from utils.embeddings import embed_texts
from utils.mongo_client import get_db

import numpy as np

VECTORS_DIR = Path(os.environ.get("VECTORS_DIR", "./vectors")).resolve()
VECTORS_DIR.mkdir(parents=True, exist_ok=True)

_stores: Dict[str, LC_FAISS] = {}
_stores_lock = threading.Lock()


class SentenceTransformerEmbeddings:
    """
    Adapter wrapper that provides:
    - embed_documents(list[str]) -> list[list[float]]
    - embed_query(str) -> list[float]
    - __call__ so LangChain/FAISS code that expects a callable works
    """

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        try:
            arr = embed_texts(texts)  # numpy array (n, dim)
            return arr.tolist()
        except Exception as e:
            logger.exception("embed_documents failed: %s", e)
            raise

    def embed_query(self, text: str) -> List[float]:
        try:
            arr = embed_texts([text])  # shape (1, dim)
            return arr[0].tolist()
        except Exception as e:
            logger.exception("embed_query failed: %s", e)
            raise

    def __call__(self, texts):
        """
        Make this object callable. If given a string, return embed_query.
        If given a list of strings, return embed_documents.
        This avoids the "'... object is not callable'" error from some LangChain wrappers.
        """
        if isinstance(texts, str):
            return self.embed_query(texts)
        if isinstance(texts, (list, tuple)):
            return self.embed_documents(list(texts))
        raise TypeError("Unsupported input to SentenceTransformerEmbeddings.__call__")


_EMBEDDINGS = SentenceTransformerEmbeddings()


def _owner_dir(owner_id: str) -> Path:
    return VECTORS_DIR / f"owner_{owner_id}"


def _save_store(owner_id: str, faiss_store: LC_FAISS):
    d = _owner_dir(owner_id)
    d.mkdir(parents=True, exist_ok=True)
    faiss_store.save_local(str(d))
    logger.debug("Saved FAISS store for owner %s at %s", owner_id, str(d))


def _load_store_from_disk(owner_id: str) -> Optional[LC_FAISS]:
    d = _owner_dir(owner_id)
    if not d.exists() or not any(d.iterdir()):
        return None
    try:
        # newer langchain_community requires allow_dangerous_deserialization flag
        try:
            store = LC_FAISS.load_local(str(d), _EMBEDDINGS, allow_dangerous_deserialization=True)  # type: ignore
        except TypeError:
            store = LC_FAISS.load_local(str(d), _EMBEDDINGS)
        logger.info("Loaded FAISS store for owner %s from %s", owner_id, str(d))
        return store
    except Exception as e:
        logger.exception("Failed to load FAISS store for %s: %s", owner_id, e)
        return None


def list_loaded_owner_ids() -> List[str]:
    with _stores_lock:
        return list(_stores.keys())


def load_all_stores() -> List[str]:
    loaded = []
    for p in VECTORS_DIR.iterdir():
        if p.is_dir() and p.name.startswith("owner_"):
            owner_id = p.name[len("owner_") :]
            try:
                store = _load_store_from_disk(owner_id)
                if store:
                    with _stores_lock:
                        _stores[owner_id] = store
                    loaded.append(owner_id)
            except Exception as e:
                logger.exception("Error loading store for %s: %s", owner_id, e)
    logger.info("FAISS stores loaded for owners: %s", loaded)
    return loaded


def _rebuild_store_from_mongo(owner_id: str) -> LC_FAISS:
    """
    Recreate FAISS index from Mongo chunks for owner_id.
    """
    db = get_db()
    chunks = list(db.chunks.find({"ownerId": owner_id}))
    texts = [c.get("text", "") for c in chunks]
    metas = [
        {
            "fileId": c.get("fileId"),
            "ownerId": c.get("ownerId"),
            "chunkIndex": c.get("chunkIndex"),
            "originalName": "",
        }
        for c in chunks
    ]
    store = LC_FAISS.from_texts(texts=texts, embedding=_EMBEDDINGS, metadatas=metas)
    _save_store(owner_id, store)
    with _stores_lock:
        _stores[owner_id] = store
    logger.info("Rebuilt FAISS store for owner %s from Mongo (%d chunks)", owner_id, len(texts))
    return store


def _get_or_create_store(owner_id: str, texts: Optional[List[str]] = None, metadatas: Optional[List[Dict]] = None) -> LC_FAISS:
    with _stores_lock:
        if owner_id in _stores:
            return _stores[owner_id]

    # try load from disk
    store = _load_store_from_disk(owner_id)
    if store:
        with _stores_lock:
            _stores[owner_id] = store
        return store

    # create from provided texts
    if texts:
        store = LC_FAISS.from_texts(texts=texts, embedding=_EMBEDDINGS, metadatas=metadatas)
        _save_store(owner_id, store)
        with _stores_lock:
            _stores[owner_id] = store
        return store

    # fallback: rebuild from Mongo
    try:
        return _rebuild_store_from_mongo(owner_id)
    except Exception as e:
        logger.exception("Failed to rebuild store from Mongo for %s: %s", owner_id, e)
        raise ValueError(f"No store for owner {owner_id} and no texts provided to create one.") from e


def add_texts_to_store(owner_id: str, texts: List[str], metadatas: List[Dict]) -> int:
    if not texts:
        return 0
    try:
        try:
            store = _get_or_create_store(owner_id)
        except ValueError:
            store = _get_or_create_store(owner_id, texts=texts, metadatas=metadatas)
            try:
                count = store.index.ntotal if hasattr(store, "index") else None
                if count is None and hasattr(store, "docstore"):
                    count = len(getattr(store.docstore, "_dict", {}))
                return int(count) if count is not None else len(texts)
            except Exception:
                return len(texts)

        # add to store
        try:
            if hasattr(store, "add_texts"):
                store.add_texts(texts=texts, metadatas=metadatas)
            else:
                # try add_documents
                try:
                    store.add_documents([Document(page_content=t, metadata=m) for t, m in zip(texts, metadatas)])
                except Exception:
                    # recreate merging existing
                    existing_texts, existing_metas = [], []
                    try:
                        if hasattr(store, "docstore") and hasattr(store.docstore, "_dict"):
                            for _, v in getattr(store.docstore, "_dict").items():
                                if isinstance(v, Document):
                                    existing_texts.append(v.page_content)
                                    existing_metas.append(v.metadata or {})
                                elif isinstance(v, dict):
                                    existing_texts.append(v.get("page_content") or v.get("text") or "")
                                    existing_metas.append(v.get("metadata") or {})
                                else:
                                    existing_texts.append(str(v))
                                    existing_metas.append({})
                    except Exception:
                        logger.exception("Failed to read existing docstore while recreating store.")
                    combined_texts = existing_texts + texts
                    combined_metas = existing_metas + metadatas
                    store = LC_FAISS.from_texts(texts=combined_texts, embedding=_EMBEDDINGS, metadatas=combined_metas)
            _save_store(owner_id, store)
        except Exception as e_add:
            logger.exception("Exception while adding to store for %s: %s. Attempting rebuild.", owner_id, e_add)
            # rebuild using Mongo + provided texts as last resort
            db = get_db()
            existing = list(db.chunks.find({"ownerId": owner_id}))
            prev_texts = [c.get("text", "") for c in existing]
            prev_metas = [
                {"fileId": c.get("fileId"), "ownerId": c.get("ownerId"), "chunkIndex": c.get("chunkIndex"), "originalName": ""}
                for c in existing
            ]
            combined_texts = prev_texts + texts
            combined_metas = prev_metas + metadatas
            new_store = LC_FAISS.from_texts(texts=combined_texts, embedding=_EMBEDDINGS, metadatas=combined_metas)
            _save_store(owner_id, new_store)
            with _stores_lock:
                _stores[owner_id] = new_store
            store = new_store

        # return count
        try:
            count = None
            if hasattr(store, "index") and hasattr(store.index, "ntotal"):
                count = store.index.ntotal
            elif hasattr(store, "docstore") and hasattr(store.docstore, "_dict"):
                count = len(getattr(store.docstore, "_dict", {}))
            return int(count) if count is not None else len(texts)
        except Exception:
            return len(texts)
    except Exception as e:
        logger.exception("add_texts_to_store failed for owner %s: %s", owner_id, e)
        raise


def search_store(owner_id: str, query: str, top_k: int = 5) -> List[Tuple[Document, float]]:
    """
    Return list of (Document, score). Robustly fallback to manual FAISS search if needed.
    """
    try:
        with _stores_lock:
            store = _stores.get(owner_id)
        if store is None:
            store = _load_store_from_disk(owner_id)
            if store:
                with _stores_lock:
                    _stores[owner_id] = store
            else:
                # try rebuild
                store = _rebuild_store_from_mongo(owner_id)

        # prefer similarity_search_with_score
        try:
            if hasattr(store, "similarity_search_with_score"):
                results = store.similarity_search_with_score(query, k=top_k)
                out = []
                for doc, score in results:
                    try:
                        s = float(score)
                    except Exception:
                        s = score
                    out.append((doc, s))
                return out
        except Exception as e:
            logger.warning("similarity_search_with_score failed for owner %s: %s", owner_id, e)
            # fall through to manual faiss search

        # manual faiss search using raw embedding
        try:
            emb = _EMBEDDINGS.embed_query(query)
            xq = np.array([emb], dtype=np.float32)
            faiss_index = getattr(store, "index", None)
            if faiss_index is None:
                return []
            D, I = faiss_index.search(xq, top_k)
            # map ids to docs via store.index_to_docstore_id or store.docstore
            res = []
            index_to_docstore = getattr(store, "index_to_docstore_id", None)
            docstore_dict = getattr(getattr(store, "docstore", None), "_dict", None)
            for dist, idx in zip(D[0], I[0]):
                if idx == -1:
                    continue
                doc_obj = None
                # Try index_to_docstore mapping first
                try:
                    if index_to_docstore:
                        docstore_id = index_to_docstore[idx]
                        if docstore_dict and docstore_id in docstore_dict:
                            v = docstore_dict[docstore_id]
                            if isinstance(v, Document):
                                doc = v
                            elif isinstance(v, dict):
                                doc = Document(page_content=v.get("page_content") or v.get("text") or "", metadata=v.get("metadata") or {})
                            else:
                                doc = Document(page_content=str(v), metadata={})
                            res.append((doc, float(dist)))
                            continue
                except Exception:
                    logger.exception("Error mapping index_to_docstore_id")

                # fallback: try to fetch metadata from docstore idx position
                try:
                    if docstore_dict:
                        keys = list(docstore_dict.keys())
                        if idx < len(keys):
                            v = docstore_dict[keys[idx]]
                            if isinstance(v, Document):
                                res.append((v, float(dist)))
                                continue
                            elif isinstance(v, dict):
                                doc = Document(page_content=v.get("page_content") or v.get("text") or "", metadata=v.get("metadata") or {})
                                res.append((doc, float(dist)))
                                continue
                            else:
                                doc = Document(page_content=str(v), metadata={})
                                res.append((doc, float(dist)))
                                continue
                except Exception:
                    logger.exception("Error reading docstore dict fallback")
                # last resort: create Document with empty content and metadata if mapping fails
                res.append((Document(page_content="", metadata={}), float(dist)))
            return res
        except Exception as e:
            logger.exception("manual FAISS search failed for owner %s: %s", owner_id, e)
            return []
    except Exception as e:
        logger.exception("search_store failed for owner %s: %s", owner_id, e)
        return []


def delete_file_from_store(owner_id: str, file_id: str) -> int:
    """
    Rebuild the owner's store excluding chunks from file_id.
    Returns number of removed vectors (approx).
    """
    db = get_db()
    current_docs = list(db.chunks.find({"ownerId": owner_id}))
    remaining = list(db.chunks.find({"ownerId": owner_id, "fileId": {"$ne": file_id}}))

    texts = []
    metas = []
    for r in remaining:
        texts.append(r.get("text", ""))
        metas.append(
            {
                "fileId": r.get("fileId"),
                "ownerId": r.get("ownerId"),
                "chunkIndex": r.get("chunkIndex"),
                "originalName": "",
            }
        )

    d = _owner_dir(owner_id)
    removed = 0
    try:
        if not texts:
            # remove on-disk files
            if d.exists():
                for f in d.iterdir():
                    try:
                        f.unlink()
                    except Exception:
                        pass
                try:
                    d.rmdir()
                except Exception:
                    pass
            with _stores_lock:
                if owner_id in _stores:
                    del _stores[owner_id]
            removed = len(current_docs)
            logger.info("Rebuilt store for %s -> empty (deleted vectors).", owner_id)
            return removed

        new_store = LC_FAISS.from_texts(texts=texts, embedding=_EMBEDDINGS, metadatas=metas)
        _save_store(owner_id, new_store)
        with _stores_lock:
            _stores[owner_id] = new_store
        removed = len(current_docs) - len(remaining)
        logger.info("Rebuilt FAISS store for %s: removed %d vectors, remaining %d", owner_id, removed, len(remaining))
        return removed
    except Exception as e:
        logger.exception("Failed to rebuild FAISS store for %s after deleting file %s: %s", owner_id, file_id, e)
        raise


def debug_store_stats(owner_id: str) -> Dict[str, Any]:
    d = _owner_dir(owner_id)
    on_disk = d.exists() and any(d.iterdir())
    with _stores_lock:
        loaded = owner_id in _stores
        store = _stores.get(owner_id)
    faiss_ntotal = None
    docstore_count = None
    sample = []
    try:
        if store is not None:
            if hasattr(store, "index") and hasattr(store.index, "ntotal"):
                faiss_ntotal = int(store.index.ntotal)
            if hasattr(store, "docstore") and hasattr(store.docstore, "_dict"):
                try:
                    docstore_count = len(getattr(store.docstore, "_dict", {}))
                except Exception:
                    docstore_count = None
            try:
                if hasattr(store, "docstore") and hasattr(store.docstore, "_dict"):
                    for i, (_, v) in enumerate(getattr(store.docstore, "_dict").items()):
                        if i >= 3:
                            break
                        if isinstance(v, Document):
                            sample.append({"text": v.page_content, "metadata": v.metadata})
                        elif isinstance(v, dict):
                            sample.append({"text": v.get("page_content") or v.get("text"), "metadata": v.get("metadata")})
                        else:
                            sample.append({"text": str(v)})
            except Exception:
                pass
    except Exception:
        logger.exception("debug_store_stats failed for %s", owner_id)
    return {
        "owner_id": owner_id,
        "is_loaded": bool(loaded),
        "on_disk_exists": bool(on_disk),
        "faiss_ntotal": faiss_ntotal,
        "docstore_count": docstore_count,
        "sample": sample,
    }


def debug_search_owner(owner_id: str, query: str, top_k: int = 6) -> Dict[str, Any]:
    """
    Detailed search diagnostic. Returns steps, embedding length, manual-faiss mapping etc.
    """
    debug: Dict[str, Any] = {"owner_id": owner_id, "query": query, "top_k": top_k, "steps": []}

    with _stores_lock:
        store = _stores.get(owner_id)
    if store is None:
        step = {"action": "load_from_disk_or_rebuild", "result": None}
        debug["steps"].append(step)
        store = _load_store_from_disk(owner_id)
        if store:
            with _stores_lock:
                _stores[owner_id] = store
            step["result"] = "loaded_from_disk"
        else:
            try:
                store = _rebuild_store_from_mongo(owner_id)
                step["result"] = "rebuilt_from_mongo"
            except Exception as e:
                step["result"] = "failed_rebuild"
                step["error"] = str(e)
                debug["store_present"] = False
                return debug

    debug["store_present"] = True

    # embed query
    try:
        q_emb = _EMBEDDINGS.embed_query(query)
        debug["embedding_len"] = len(q_emb)
        debug["steps"].append({"action": "embed_query", "result": "ok"})
    except Exception as e:
        debug["steps"].append({"action": "embed_query", "result": "error", "error": str(e)})
        return debug

    # try similarity_search_with_score
    try:
        if hasattr(store, "similarity_search_with_score"):
            res = store.similarity_search_with_score(query, k=top_k)
            debug["steps"].append({"action": "similarity_search_with_score", "count": len(res)})
            serial = []
            for doc, score in res:
                serial.append({"text": getattr(doc, "page_content", None), "score": float(score)})
            debug["similarity_search_with_score"] = serial
            if res:
                return debug
    except Exception as e:
        debug["steps"].append({"action": "similarity_search_with_score", "error": str(e)})

    # manual FAISS search
    try:
        if hasattr(store, "index") and getattr(store.index, "ntotal", 0) > 0:
            xq = np.array([q_emb], dtype=np.float32)
            faiss_index = getattr(store, "index", None)
            D, I = faiss_index.search(xq, top_k)
            D = D.tolist() if hasattr(D, "tolist") else D
            I = I.tolist() if hasattr(I, "tolist") else I
            debug["steps"].append({"action": "manual_faiss_search", "distances": D, "ids": I})
            # mapping ids back to docs
            mapped = []
            index_to_docstore = getattr(store, "index_to_docstore_id", None)
            docstore_dict = getattr(getattr(store, "docstore", None), "_dict", None)
            for dist, idx in zip(D[0], I[0]):
                if idx == -1:
                    mapped.append({"id": None, "distance": float(dist), "doc": None})
                    continue
                doc_obj = None
                doc_meta = None
                try:
                    if index_to_docstore:
                        docstore_id = index_to_docstore[idx]
                        if docstore_dict and docstore_id in docstore_dict:
                            v = docstore_dict[docstore_id]
                            if isinstance(v, Document):
                                doc_obj = v.page_content
                                doc_meta = v.metadata
                            elif isinstance(v, dict):
                                doc_obj = v.get("page_content") or v.get("text")
                                doc_meta = v.get("metadata")
                            else:
                                doc_obj = str(v)
                    else:
                        if docstore_dict:
                            keys = list(docstore_dict.keys())
                            if idx < len(keys):
                                v = docstore_dict[keys[idx]]
                                if isinstance(v, Document):
                                    doc_obj = v.page_content
                                    doc_meta = v.metadata
                                elif isinstance(v, dict):
                                    doc_obj = v.get("page_content") or v.get("text")
                                    doc_meta = v.get("metadata")
                                else:
                                    doc_obj = str(v)
                except Exception:
                    logger.exception("Error mapping faiss idx -> docstore")
                mapped.append({"id": idx, "distance": float(dist), "doc": doc_obj, "meta": doc_meta})
            debug["manual_faiss_map"] = mapped
            return debug
    except Exception as e:
        debug["steps"].append({"action": "manual_faiss_search", "error": str(e)})

    debug["steps"].append({"action": "no_results", "result": True})
    return debug
