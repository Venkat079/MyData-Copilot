import React from "react";
import "../styles/components.css";

export default function FilePreview({ file }) {
  if (!file) return null;
  const ext = (file.name || "").split(".").pop().toLowerCase();

  if (["png", "jpg", "jpeg", "gif", "webp"].includes(ext)) {
    return (
      <img
        src={file.previewUrl || file.url}
        alt={file.name}
        className="file-preview-image"
      />
    );
  }

  if (["mp4", "webm"].includes(ext)) {
    return (
      <video controls className="file-preview-video">
        <source src={file.previewUrl || file.url} />
      </video>
    );
  }

  return (
    <div className="file-preview-other">
      <p>{file.name}</p>
      <a href={file.url} target="_blank" rel="noreferrer">
        Download
      </a>
    </div>
  );
}
