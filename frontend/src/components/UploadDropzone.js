import React, { useRef, useState } from "react";
import "../styles/components.css";

export default function UploadDropzone({ onUploaded }) {
  const fileRef = useRef();
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);

  async function handleFiles(files) {
    if (!files || files.length === 0) return;
    const file = files[0];
    const fd = new FormData();
    fd.append("file", file);

    setUploading(true);
    setProgress(0);

    try {
      const onProgress = (p) => setProgress(p);
      const api = await import("../api/api");
      // FIX: call root of /api/upload
      const res = await api.upload("/upload", fd, onProgress);
      setProgress(100);
      setTimeout(() => setUploading(false), 500);
      if (onUploaded) onUploaded(res);
    } catch (err) {
      console.error("Upload failed", err);
      setUploading(false);
      alert("Upload failed. Check console for details.");
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    handleFiles(e.dataTransfer.files);
  }

  function handleSelect(e) {
    handleFiles(e.target.files);
  }

  return (
    <div>
      <div
        className="dropzone"
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        onClick={() => fileRef.current.click()}
        role="button"
      >
        <input
          ref={fileRef}
          type="file"
          className="hidden"
          onChange={handleSelect}
        />
        <div className="dropzone-inner">
          <p>Drag & drop a file here, or click to select</p>
          <small>
            Supported: PDF, DOCX, PPTX, TXT, images, audio, video, CSV
          </small>
        </div>
      </div>

      {uploading && (
        <div className="upload-progress">
          <div className="bar" style={{ width: progress + "%" }} />
          <span>{progress}%</span>
        </div>
      )}
    </div>
  );
}
