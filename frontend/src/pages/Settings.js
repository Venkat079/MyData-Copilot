import React from "react";
import { clearToken } from "../utils/auth";
import "../styles/components.css";

export default function Settings() {
  function handleLogoutClear() {
    if (window.confirm("Clear local session and go to login?")) {
      clearToken();
      window.location.href = "/login";
    }
  }

  return (
    <div className="page-container">
      <h2>Settings</h2>
      <div className="settings-card">
        <h4>Account</h4>
        <div>
          <button className="btn-ghost" onClick={handleLogoutClear}>
            Logout & clear local session
          </button>
        </div>
      </div>
      <div className="settings-card">
        <h4>Data</h4>
        <p className="muted">
          Data lifecycle, export and deletion should be managed server-side. Use
          the backend admin endpoints for full control.
        </p>
      </div>
    </div>
  );
}
