# python-rag/app.py
import os
import uuid
import logging
import requests
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from dotenv import load_dotenv

from langchain.text_splitter import RecursiveCharacterTextSplitter

from utils.file_processing import extract_text_simple
from utils.vector_store import (
    add_texts_to_store,
    search_store,
    load_all_stores,
    list_loaded_owner_ids,
    delete_file_from_store,
    debug_store_stats,
    debug_search_owner,
)
from utils.mongo_client import get_db

import uvicorn

load_dotenv()  # load .env if present

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("python-rag")

app = FastAPI()
db = get_db()

OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# Optional Gemini config
GEMINI_API_URL = os.environ.get("GEMINI_API_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# small heuristic summarizer fallback
def simple_summarize_chunks(retrieved: list, max_sentences: int = 3) -> str:
    """
    Heuristic fallback summarizer:
     - look for lines containing 'skill' or 'technical' and return those bullets
     - otherwise take first N sentences from top chunks
    """
    import re
    bullets = []
    for r in retrieved:
        text = r.get("text", "")
        # try to find a 'Technical Skills' section or lines starting with bullet markers
        for m in re.finditer(r"(Technical Skills[:\s]*\n?(.+?)(?:\n\n|\n[A-Z]|\Z))", text, flags=re.IGNORECASE | re.DOTALL):
            # take the found block, split lines, keep lines containing words
            block = m.group(2)
            for ln in block.splitlines():
                ln = ln.strip(" -•\t\r\n")
                if len(ln) > 3:
                    bullets.append(ln)
            if bullets:
                # return unique bullets
                seen = []
                out = []
                for b in bullets:
                    if b not in seen:
                        seen.append(b)
                        out.append(b)
                return "Skills (extracted):\n- " + "\n- ".join(out[:20])
    # fallback: first sentences
    all_text = " ".join([r.get("text","") for r in retrieved])[:3000]
    # naive sentence split
    sents = re.split(r'(?<=[.!?])\s+', all_text)
    sents = [s.strip() for s in sents if s.strip()]
    if not sents:
        return "No concise summary could be generated from retrieved content; here are the retrieved snippets."
    return "Summary (heuristic): " + " ".join(sents[:max_sentences])



def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    if not text:
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", " ", ""],
    )
    return splitter.split_text(text)


# Schemas
class ProcessFilePayload(BaseModel):
    file_id: str
    owner_id: str
    path: str
    original_name: Optional[str]


class DeletePayload(BaseModel):
    file_id: str
    owner_id: str


class QueryPayload(BaseModel):
    query: str
    scope: Optional[str] = "mydata+general"
    owner_id: str


class ChatPayload(BaseModel):
    query: str
    owner_id: str
    top_k: int = 4
    temperature: float = 0.2
    max_tokens: int = 300
    scope: Optional[str] = "mydata+general"
    selected_models: Optional[List[str]] = None  # ["openai","gemini"]


@app.on_event("startup")
def on_startup_load_vectorstores():
    try:
        loaded = load_all_stores()
        if loaded:
            logger.info("Loaded vector stores for owners: %s", ", ".join(loaded))
        else:
            logger.info("No existing vector stores found on disk.")
    except Exception as e:
        logger.exception("Failed to load vector stores on startup: %s", e)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/vector-stores")
def vector_stores():
    try:
        return {"loaded": list_loaded_owner_ids()}
    except Exception as e:
        logger.exception("Error listing vector stores: %s", e)
        raise HTTPException(status_code=500, detail="failed to list vector stores")


@app.post("/process-file")
def process_file(payload: ProcessFilePayload):
    p = payload.path
    if not os.path.exists(p):
        raise HTTPException(status_code=400, detail="file not found on server")

    text = extract_text_simple(p)
    if not text:
        logger.info("No extractable text for %s", p)
        return {"ok": True, "message": "no text extracted"}

    chunks = chunk_text(text, chunk_size=1200, overlap=200)
    if not chunks:
        return {"ok": True, "message": "no chunks"}

    metas = [
        {
            "fileId": payload.file_id,
            "ownerId": payload.owner_id,
            "chunkIndex": i,
            "originalName": payload.original_name or "",
        }
        for i in range(len(chunks))
    ]

    try:
        count_after = add_texts_to_store(owner_id=payload.owner_id, texts=chunks, metadatas=metas)
        logger.info(
            "Added %d chunks to vector store for owner %s (count after: %s)",
            len(chunks),
            payload.owner_id,
            count_after,
        )
    except Exception as e:
        logger.exception("Failed to add texts to vector store: %s", e)
        raise HTTPException(status_code=500, detail="vector store update failed")

    docs = []
    for i, c in enumerate(chunks):
        docs.append(
            {
                "id": str(uuid.uuid4()),
                "fileId": payload.file_id,
                "ownerId": payload.owner_id,
                "text": c,
                "chunkIndex": i,
            }
        )
    if docs:
        try:
            db.chunks.insert_many(docs)
        except Exception as e:
            logger.exception("Failed to insert chunks into Mongo: %s", e)
            return {"ok": False, "message": "vectors stored but failed to save chunks metadata"}

    logger.info("Processed file %s: %d chunks", payload.original_name, len(chunks))
    return {"ok": True, "count": len(chunks)}


@app.post("/delete-file")
def delete_file_post(payload: DeletePayload):
    return _delete_file_logic(payload.file_id, payload.owner_id)


@app.delete("/delete-file")
def delete_file_delete(file_id: Optional[str] = None, owner_id: Optional[str] = None):
    if not file_id or not owner_id:
        raise HTTPException(status_code=400, detail="file_id and owner_id required")
    return _delete_file_logic(file_id, owner_id)


def _delete_file_logic(file_id: str, owner_id: str):
    try:
        res = db.chunks.delete_many({"fileId": file_id, "ownerId": owner_id})
        logger.info("Deleted %d chunk docs for file %s", res.deleted_count, file_id)
    except Exception as e:
        logger.exception("Failed to delete chunks in Mongo: %s", e)
        raise HTTPException(status_code=500, detail="failed to delete chunks from db")

    try:
        removed = delete_file_from_store(owner_id=owner_id, file_id=file_id)
        return {"ok": True, "deleted_from_vector_store": removed}
    except Exception as e:
        logger.exception("Failed to remove vectors for file: %s", e)
        return {"ok": False, "message": "Mongo cleaned but failed to update vector store"}


@app.post("/query")
def query(payload: QueryPayload):
    q = (payload.query or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="query required")

    hits = search_store(owner_id=payload.owner_id, query=q, top_k=6)

    if hits and (payload.scope in ["mydata", "mydata+general", None]):
        snippets = []
        citations = []
        for doc, score in hits:
            md = doc.metadata or {}
            file_id = md.get("fileId")
            chunk_index = md.get("chunkIndex")
            file = db.files.find_one({"id": file_id}) or {}
            title = file.get("originalName") or md.get("originalName") or "unknown"
            chunk_doc = db.chunks.find_one({"fileId": file_id, "ownerId": payload.owner_id, "chunkIndex": chunk_index})
            text = (chunk_doc.get("text") if chunk_doc else doc.page_content) or ""
            text = text[:1200]
            snippets.append(f"From {title} (chunk {chunk_index}, score {score:.3f}):\n{text}")
            citations.append({"title": title, "locator": f"chunk {chunk_index}", "score": score})
        answer = "\n\n---\n\n".join(snippets)
        return {"message": answer, "answer_origin": "user-data", "citations": citations, "confidence": "medium"}

    return {"message": "No answer found in your database. (General fallback not configured.)", "answer_origin": "general-knowledge", "citations": [], "confidence": "low"}


def call_gemini(prompt: str, context: str = "", temperature: float = 0.3, max_tokens: int = 4096) -> Dict[str, Any]:
    """
    Calls Gemini 2.5 Flash via REST API.
    Handles long context, truncation retries, and partial responses.
    """
    import os, requests

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-05-20")
    gemini_api_url = os.getenv("GEMINI_API_URL", "https://generativelanguage.googleapis.com/v1beta")

    if not gemini_api_key or not gemini_api_url:
        return {"ok": False, "error": "GEMINI not configured (GEMINI_API_URL/GEMINI_API_KEY missing)"}

    # Trim context to avoid exceeding Gemini’s 8K-16K input limit
    if len(context) > 8000:
        context = context[:8000]

    url = f"{gemini_api_url}/models/{gemini_model}:generateContent?key={gemini_api_key}"
    headers = {"Content-Type": "application/json"}

    full_prompt = (
        f"You are an assistant answering based on the provided context.\n"
        f"Use the context if relevant; if not, respond generally but factually.\n\n"
        f"Context:\n{context}\n\nQuestion:\n{prompt}"
    )

    body = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "topP": 0.95,
            "topK": 40
        }
    }

    def extract_text(data):
        """Safely extract text from Gemini response JSON."""
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        for p in parts:
            if "text" in p:
                return p["text"]
        return ""

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=60)
        data = resp.json()

        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text}", "raw": data}

        text_output = extract_text(data).strip()
        finish_reason = data.get("candidates", [{}])[0].get("finishReason", "")

        # ✅ Retry if Gemini stopped early (output truncated)
        if finish_reason == "MAX_TOKENS" or not text_output:
            short_context = context[:2000]
            retry_body = body.copy()
            retry_body["contents"][0]["parts"][0]["text"] = (
                f"(Context shortened to fit)\n\n{short_context}\n\nQuestion:\n{prompt}"
            )
            retry_body["generationConfig"]["maxOutputTokens"] = 2048
            retry_resp = requests.post(url, headers=headers, json=retry_body, timeout=60)
            retry_data = retry_resp.json()
            retry_text = extract_text(retry_data).strip()
            if retry_text:
                text_output = retry_text + "\n\n(Note: Gemini output was truncated initially; this is a shorter retry.)"

        if not text_output:
            text_output = "(Gemini produced no visible text output.)"

        return {"ok": True, "content": text_output, "raw": data}

    except Exception as e:
        return {"ok": False, "error": str(e)}



@app.post("/chat")
def chat(payload: ChatPayload):
    """
    Retrieve top-k chunks from user's FAISS store, call selected LLMs (OpenAI/Gemini)
    to synthesize answers using those chunks as context, and return responses plus
    retrieved citations. If LLMs fail or are not configured, return a heuristic
    fallback summary built from retrieved chunks (so the user still gets an answer).
    """
    try:
        q = (payload.query or "").strip()
        if not q:
            raise HTTPException(status_code=400, detail="query required")

        owner = payload.owner_id
        top_k = max(1, int(payload.top_k or 4))
        selected = [m.lower() for m in (payload.selected_models or ["openai", "gemini"])]

        # 1) Retrieve top-k from vector store
        hits = search_store(owner_id=owner, query=q, top_k=top_k)

        # Build retrieved snippets (try to fetch full chunk text from Mongo when possible)
        retrieved = []
        for i, (doc, score) in enumerate(hits):
            md = doc.metadata or {}
            file_id = md.get("fileId")
            chunk_index = md.get("chunkIndex")
            chunk_text = None

            # Try chunk id if present
            chunk_id = md.get("chunkId") or md.get("id")
            if chunk_id:
                chunk_doc = db.chunks.find_one({"id": chunk_id})
                if chunk_doc:
                    chunk_text = chunk_doc.get("text", "")

            # Fallback to fileId+chunkIndex lookup
            if not chunk_text and file_id is not None and chunk_index is not None:
                chunk_doc = db.chunks.find_one({"fileId": file_id, "ownerId": owner, "chunkIndex": chunk_index})
                if chunk_doc:
                    chunk_text = chunk_doc.get("text", "")

            # Final fallback: use the langchain Document page_content
            if not chunk_text:
                chunk_text = getattr(doc, "page_content", "") or ""

            # Resolve file title if possible
            title = ""
            if file_id:
                f = db.files.find_one({"id": file_id}) or {}
                title = f.get("originalName") or f.get("name") or md.get("originalName") or ""

            retrieved.append({
                "chunkId": chunk_id,
                "fileId": file_id,
                "fileTitle": title,
                "chunkIndex": chunk_index,
                "score": float(score or 0.0),
                "text": (chunk_text or "")[:1600],  # truncate to keep prompts reasonable
            })

        # Prepare context text for LLMs
        ctx_parts = []
        for idx, r in enumerate(retrieved, start=1):
            hdr = f"[{idx}] Source: {r['fileTitle'] or 'unknown'} (chunk {r.get('chunkIndex', '?')}, score {r['score']:.3f})"
            ctx_parts.append(hdr + "\n" + r["text"])
        context_text = "\n\n---\n\n".join(ctx_parts)

        responses = []

        # If retrieved chunks exist and the scope allows using user-data
        if retrieved and (payload.scope in ["mydata", "mydata+general", None]):
            # OpenAI (if selected)
            if "openai" in selected:
                if OPENAI_KEY:
                    system_msg = (
                        "You are an assistant that answers questions using the provided user documents. "
                        "Use ONLY the information present in the provided documents to answer the question. "
                        "If the answer is not contained in the documents, say that you could not find the answer in the documents. "
                        "Be concise and show citations like [1], [2] where appropriate."
                    )
                    user_msg = f"QUESTION: {q}\n\nCONTEXT:\n{context_text}\n\nAnswer concisely and cite sources by number."
                    try:
                        headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
                        body = {
                            "model": OPENAI_MODEL,
                            "messages": [
                                {"role": "system", "content": system_msg},
                                {"role": "user", "content": user_msg},
                            ],
                            "max_tokens": int(payload.max_tokens or 300),
                            "temperature": float(payload.temperature or 0.2),
                        }
                        r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body, timeout=30)
                        if r.status_code == 200:
                            j = r.json()
                            content = j.get("choices", [{}])[0].get("message", {}).get("content", "")
                            responses.append({"model": "openai", "ok": True, "content": content, "meta": {"provider": "openai"}})
                        else:
                            logger.warning("OpenAI non-200: %s %s", r.status_code, r.text)
                            responses.append({"model": "openai", "ok": False, "error": f"status {r.status_code}", "raw": r.text})
                    except Exception as e:
                        logger.exception("OpenAI call failed: %s", e)
                        responses.append({"model": "openai", "ok": False, "error": str(e)})
                else:
                    responses.append({"model": "openai", "ok": False, "error": "OPENAI_KEY not set"})

            # Gemini (if selected)
            if "gemini" in selected:
                if GEMINI_API_URL and GEMINI_API_KEY:
                    gem = call_gemini(prompt=q, context=context_text, temperature=float(payload.temperature or 0.2), max_tokens=int(payload.max_tokens or 300))
                    if gem.get("ok"):
                        responses.append({"model": "gemini", "ok": True, "content": gem.get("content"), "meta": {"provider": "gemini"}})
                    else:
                        responses.append({"model": "gemini", "ok": False, "error": gem.get("error"), "raw": gem.get("raw")})
                else:
                    responses.append({"model": "gemini", "ok": False, "error": "GEMINI not configured (GEMINI_API_URL/GEMINI_API_KEY missing)"})

            # If none of the selected LLMs returned a successful result, provide a heuristic fallback summary
            if not any(r.get("ok") for r in responses if r.get("model") in ("openai", "gemini")):
                # produce fallback summary from retrieved chunks so user still gets an answer
                fallback_answer = simple_summarize_chunks(retrieved, max_sentences=4)
                return {
                    "message": fallback_answer,
                    "answer_origin": "user-data-fallback",
                    "retrieved": retrieved,
                    "responses": responses,
                    "retrieval_hits": len(retrieved),
                }

            # At least one model succeeded — return collected responses + retrieved
            return {
                "message": "Responses generated",
                "answer_origin": "user-data",
                "retrieved": retrieved,
                "responses": responses,
                "retrieval_hits": len(retrieved),
            }

        # If no retrieved chunks or user requested general-only -> fallback to general LLMs (no context)
        fallback_responses = []
        if "openai" in (payload.selected_models or ["openai"]):
            if OPENAI_KEY:
                try:
                    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
                    body = {
                        "model": OPENAI_MODEL,
                        "messages": [{"role": "user", "content": f"Answer concisely:\n\n{q}"}],
                        "max_tokens": int(payload.max_tokens or 300),
                        "temperature": float(payload.temperature or 0.2),
                    }
                    r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body, timeout=30)
                    if r.status_code == 200:
                        j = r.json()
                        content = j.get("choices", [{}])[0].get("message", {}).get("content", "")
                        fallback_responses.append({"model": "openai", "ok": True, "content": content})
                    else:
                        logger.warning("OpenAI non-200: %s %s", r.status_code, r.text)
                        fallback_responses.append({"model": "openai", "ok": False, "error": f"status {r.status_code}", "raw": r.text})
                except Exception as e:
                    logger.exception("OpenAI fallback failed: %s", e)
                    fallback_responses.append({"model": "openai", "ok": False, "error": str(e)})
            else:
                fallback_responses.append({"model": "openai", "ok": False, "error": "OPENAI_KEY not set"})

        if "gemini" in (payload.selected_models or ["gemini"]):
            if GEMINI_API_URL and GEMINI_API_KEY:
                gem = call_gemini(prompt=q, context="", temperature=float(payload.temperature or 0.2), max_tokens=int(payload.max_tokens or 300))
                if gem.get("ok"):
                    fallback_responses.append({"model": "gemini", "ok": True, "content": gem.get("content")})
                else:
                    fallback_responses.append({"model": "gemini", "ok": False, "error": gem.get("error")})
            else:
                fallback_responses.append({"model": "gemini", "ok": False, "error": "GEMINI not configured"})

        if fallback_responses:
            return {
                "message": "General fallback responses",
                "answer_origin": "general-knowledge",
                "responses": fallback_responses,
                "retrieval_hits": 0,
            }

        # final fallback: no retrieved content & no LLMs configured/successful
        return {
            "message": "No answer found in your database. (General fallback not configured.)",
            "answer_origin": "none",
            "responses": responses,
            "retrieval_hits": len(retrieved),
        }

    except HTTPException:
        # re-raise FastAPI HTTPExceptions
        raise
    except Exception as e:
        logger.exception("Chat endpoint failed: %s", e)
        # give the frontend a helpful error message rather than 500 stack trace
        raise HTTPException(status_code=500, detail=f"chat failed: {e}")


# Debug endpoints
@app.get("/debug-store/{owner_id}")
def debug_store(owner_id: str):
    try:
        stats = debug_store_stats(owner_id)
        return {"ok": True, "debug": stats}
    except Exception as e:
        logger.exception("debug-store failed: %s", e)
        return {"ok": False, "error": str(e)}


@app.post("/debug-search")
def debug_search(payload: QueryPayload):
    try:
        debug = debug_search_owner(payload.owner_id, payload.query, top_k=6)
        return {"ok": True, "debug_search": debug}
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.exception("debug-search failed: %s", e)
        return {"ok": False, "error": str(e), "traceback": tb}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=True)
