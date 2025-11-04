import React, { useEffect, useState } from "react";
import "../styles/components.css";
import * as api from "../api/api";

// helper: decode JWT payload (no verification) to find an id/sub/userId
function decodeJwtPayload(token) {
  if (!token) return null;
  try {
    const parts = token.split(".");
    if (parts.length < 2) return null;
    const payload = parts[1];
    // base64url -> padded base64
    const b64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
    const json = atob(padded);
    return JSON.parse(json);
  } catch (e) {
    return null;
  }
}

export default function ChatBox({ initialContext = {} }) {
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState("mydata+general");
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [ownerId, setOwnerId] = useState(null);

  const [useOpenAI, setUseOpenAI] = useState(true);
  const [useGemini, setUseGemini] = useState(false);

  // load owner id: try /me -> /me/stats -> decode JWT
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        // try /me
        const me = await api.get("/me").catch(() => null);
        if (mounted && me && (me.id || (me.user && me.user.id))) {
          setOwnerId(me.id || (me.user && me.user.id));
          return;
        }

        // try /me/stats
        const stats = await api.get("/me/stats").catch(() => null);
        if (mounted && stats && stats.ownerId) {
          setOwnerId(stats.ownerId);
          return;
        }

        // fallback: decode token in localStorage (jwtToken or token)
        const token =
          localStorage.getItem("jwtToken") ||
          localStorage.getItem("token") ||
          localStorage.getItem("jwt") ||
          null;
        if (token) {
          const p = decodeJwtPayload(token);
          if (p) {
            // common claim names: id, sub, user_id, userId
            const candidate =
              p.id || p.sub || p.userId || p.user_id || (p.user && p.user.id);
            if (candidate) {
              setOwnerId(candidate);
              // also persist fallback
              localStorage.setItem("ownerId", candidate);
              return;
            }
          }
        }

        // fallback to explicitly saved ownerId (if present)
        const saved = localStorage.getItem("ownerId");
        if (saved) setOwnerId(saved);
      } catch (e) {
        // ignore
      }
    })();
    return () => (mounted = false);
  }, []);

  async function handleSend(e) {
    e?.preventDefault();
    const q = query.trim();
    if (!q) return;

    if (!ownerId) {
      alert(
        "No ownerId found. Make sure you are logged in or backend /me returns your id."
      );
      return;
    }

    const id = Date.now();
    const entry = { id, question: q, status: "pending" };
    setHistory((h) => [entry, ...h]);
    setLoading(true);
    setQuery("");

    try {
      const selected_models = [];
      if (useOpenAI) selected_models.push("openai");
      if (useGemini) selected_models.push("gemini");

      const body = {
        query: q,
        owner_id: ownerId,
        top_k: 4,
        temperature: 0.2,
        max_tokens: 300,
        scope,
        selected_models,
      };

      const res = await api.post("/chat", body);
      const updated = { ...entry, status: "done", response: res };
      setHistory((h) => [updated, ...h.slice(1)]);
    } catch (err) {
      const updated = {
        ...entry,
        status: "error",
        error: err?.message || JSON.stringify(err),
      };
      setHistory((h) => [updated, ...h.slice(1)]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chatbox">
      <form className="chat-form" onSubmit={handleSend}>
        <div
          className="chat-controls"
          style={{ display: "flex", gap: 12, alignItems: "center" }}
        >
          <select value={scope} onChange={(e) => setScope(e.target.value)}>
            <option value="mydata">My Data Only</option>
            <option value="mydata+general">My Data + General</option>
            <option value="general">General Only</option>
          </select>

          <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input
              type="checkbox"
              checked={useOpenAI}
              onChange={(e) => setUseOpenAI(e.target.checked)}
            />{" "}
            OpenAI
          </label>

          <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input
              type="checkbox"
              checked={useGemini}
              onChange={(e) => setUseGemini(e.target.checked)}
            />{" "}
            Gemini
          </label>

          <button className="btn" type="submit" disabled={loading}>
            {loading ? "Thinking..." : "Ask"}
          </button>
        </div>

        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask about your uploaded files, or general knowledge..."
          rows="3"
        />
      </form>

      <div className="chat-history">
        {history.map((h) => (
          <div className="chat-item" key={h.id}>
            <div className="chat-question">{h.question}</div>
            <div className="chat-response">
              {h.status === "pending" && <em>Waiting for answer…</em>}
              {h.status === "error" && (
                <span className="error">Error: {h.error}</span>
              )}
              {h.status === "done" && (
                <>
                  <div
                    className="response-meta"
                    style={{ display: "flex", gap: 12, flexWrap: "wrap" }}
                  >
                    <small>
                      origin:{" "}
                      {h.response.answer_origin ||
                        h.response.origin ||
                        "unknown"}
                    </small>
                    {h.response.confidence && (
                      <small>confidence: {h.response.confidence}</small>
                    )}
                    {h.response.retrieval_hits !== undefined && (
                      <small>retrieval_hits: {h.response.retrieval_hits}</small>
                    )}
                  </div>

                  {h.response.responses &&
                    Array.isArray(h.response.responses) && (
                      <div
                        className="responses-grid"
                        style={{
                          display: "grid",
                          gridTemplateColumns:
                            "repeat(auto-fit,minmax(300px,1fr))",
                          gap: 12,
                        }}
                      >
                        {h.response.responses.map((r, i) => (
                          <div
                            key={i}
                            className="llm-card"
                            style={{
                              border: "1px solid #ddd",
                              padding: 12,
                              borderRadius: 6,
                            }}
                          >
                            <strong>{r.model}</strong>
                            <div style={{ marginTop: 8 }}>
                              {r.ok ? (
                                <div style={{ whiteSpace: "pre-wrap" }}>
                                  {r.content}
                                </div>
                              ) : (
                                <div style={{ color: "red" }}>
                                  Error: {r.error || JSON.stringify(r.raw)}
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                  {h.response.message && (
                    <div style={{ marginTop: 8, whiteSpace: "pre-wrap" }}>
                      {h.response.message}
                    </div>
                  )}

                  {h.response.citations && h.response.citations.length > 0 && (
                    <div className="citations">
                      <strong>Sources:</strong>
                      <ul>
                        {h.response.citations.map((c, i) => (
                          <li key={i}>
                            {c.title} {c.locator ? `(${c.locator})` : ""}{" "}
                            {c.url && (
                              <a href={c.url} target="_blank" rel="noreferrer">
                                open
                              </a>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {h.response.retrieved && h.response.retrieved.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <strong>Retrieved chunks:</strong>
                      <ul>
                        {h.response.retrieved.map((r, idx) => (
                          <li key={idx}>
                            <small>
                              {r.fileTitle || r.fileId} - chunk {r.chunkIndex} -
                              score {r.score.toFixed(3)}
                            </small>
                            <div
                              style={{
                                whiteSpace: "pre-wrap",
                                maxHeight: 120,
                                overflow: "auto",
                              }}
                            >
                              {r.text}
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        ))}
        {history.length === 0 && (
          <div className="empty">
            No questions yet. Ask something about your data.
          </div>
        )}
      </div>
    </div>
  );
}
