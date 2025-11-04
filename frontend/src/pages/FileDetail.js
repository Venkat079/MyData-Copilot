import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { get } from "../api/api";
import FilePreview from "../components/FilePreview";
import "../styles/components.css";

export default function FileDetail() {
  const { id } = useParams();
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const res = await get(`/files/${id}`);
        setFile(res.file || res);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  if (loading) return <div className="page-container">Loading...</div>;
  if (!file) return <div className="page-container">File not found</div>;

  return (
    <div className="page-container file-detail">
      <div className="file-detail-left">
        <FilePreview file={file} />
      </div>
      <div className="file-detail-right">
        <h3>{file.name}</h3>
        <p>
          <strong>Type:</strong> {file.type || "file"}
        </p>
        <p>
          <strong>Size:</strong> {file.size} bytes
        </p>
        <p>
          <strong>Uploaded:</strong>{" "}
          {new Date(
            file.createdAt || file.created_at || Date.now()
          ).toLocaleString()}
        </p>
        <div className="file-actions-vertical">
          <a
            className="btn-ghost"
            href={file.url}
            target="_blank"
            rel="noreferrer"
          >
            Open / Download
          </a>
          <button
            className="btn"
            onClick={() => alert("Trigger reindex (backend endpoint needed)")}
          >
            Reindex
          </button>
        </div>

        <div className="file-chunks">
          <h4>Indexed segments (preview)</h4>
          {file.chunks && file.chunks.length > 0 ? (
            file.chunks.slice(0, 8).map((c, i) => (
              <div key={i} className="chunk">
                {c.text || c.content || "(no text)"}
              </div>
            ))
          ) : (
            <div className="muted">No preview available.</div>
          )}
        </div>
      </div>
    </div>
  );
}
