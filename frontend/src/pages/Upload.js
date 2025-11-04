import React, { useState } from "react";
import UploadDropzone from "../components/UploadDropzone";
import "../styles/components.css";
// ❌ removed unused import { get }
import { useNavigate } from "react-router-dom";

export default function Upload() {
  const [last, setLast] = useState(null);
  const navigate = useNavigate();

  async function handleUploaded(res) {
    setLast(res);
    // Optionally refresh file list; navigate to files
    setTimeout(() => {
      navigate("/files");
    }, 700);
  }

  return (
    <div className="page-container">
      <h2>Upload files</h2>
      <p className="muted">
        Supported: PDF, DOCX, PPTX, TXT, images, audio, video, CSV
      </p>
      <UploadDropzone onUploaded={handleUploaded} />
      {last && (
        <div className="upload-result">
          <strong>Uploaded:</strong>{" "}
          {last.fileName || last.name || "File uploaded"}
        </div>
      )}
    </div>
  );
}
