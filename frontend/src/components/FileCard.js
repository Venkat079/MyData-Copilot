// src/components/FileCard.js
import React from "react";
import { Link } from "react-router-dom";
import { formatBytes } from "../utils/helpers";
import "../styles/components.css";

export default function FileCard({ file, onDelete }) {
  return (
    <div className="file-card">
      <div className="file-meta">
        <strong className="file-name">{file.name}</strong>
        <div className="file-info">
          <span>{file.type || "file"}</span>
          <span>{formatBytes(file.size)}</span>
          <span>
            {new Date(
              file.createdAt || file.created_at || Date.now()
            ).toLocaleDateString()}
          </span>
        </div>
      </div>
      <div className="file-actions">
        <Link to={`/files/${file.id || file._id}`}>Open</Link>
        {onDelete && (
          <button
            className="delete-btn"
            onClick={() => onDelete(file.id || file._id)}
            title="Delete file"
          >
            🗑️
          </button>
        )}
      </div>
    </div>
  );
}
