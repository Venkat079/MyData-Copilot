// src/pages/Files.js
import React, { useEffect, useState } from "react";
import { get, del } from "../api/api"; // <-- include del
import FileCard from "../components/FileCard";
import "../styles/components.css";

export default function Files() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadFiles();
  }, []);

  async function loadFiles() {
    setLoading(true);
    try {
      const res = await get("/files");
      setFiles(res.files || res || []);
    } catch (err) {
      console.error("Failed to fetch files", err);
    } finally {
      setLoading(false);
    }
  }

  const handleDelete = async (fileId) => {
    if (!window.confirm("Delete this file?")) return;
    try {
      const result = await del(`/files/${fileId}`);
      if (result.ok) {
        setFiles(files.filter((f) => f.id !== fileId && f._id !== fileId));
      }
    } catch (err) {
      alert("Failed to delete file: " + err.message);
    }
  };

  return (
    <div className="page-container">
      <h2>Your files</h2>
      {loading && <div>Loading...</div>}
      {!loading && files.length === 0 && (
        <div className="empty">
          No files uploaded yet. Upload one on the Upload page.
        </div>
      )}
      <div className="files-grid">
        {files.map((f) => (
          <FileCard key={f.id || f._id} file={f} onDelete={handleDelete} />
        ))}
      </div>
    </div>
  );
}
