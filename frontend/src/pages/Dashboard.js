import React, { useEffect, useState } from "react";
import ChatBox from "../components/ChatBox";
import { get } from "../api/api";
import "../styles/dashboard.css";

export default function Dashboard() {
  const [stats, setStats] = useState({ files: 0, pages: 0, lastUpload: null });

  useEffect(() => {
    async function load() {
      try {
        const res = await get("/me/stats");
        setStats({
          files: res.files || 0,
          pages: res.pages || 0,
          lastUpload: res.lastUpload || null,
        });
      } catch (e) {
        // ignore
      }
    }
    load();
  }, []);

  return (
    <div className="dashboard-page">
      <div className="dashboard-top">
        <div className="stat-card">
          <h3>{stats.files}</h3>
          <p>Files indexed</p>
        </div>
        <div className="stat-card">
          <h3>{stats.pages}</h3>
          <p>Pages / segments</p>
        </div>
        <div className="stat-card">
          <h3>
            {stats.lastUpload
              ? new Date(stats.lastUpload).toLocaleString()
              : "—"}
          </h3>
          <p>Last upload</p>
        </div>
      </div>

      <div className="dashboard-main">
        <div className="chat-column">
          <h4>Ask your data</h4>
          <ChatBox />
        </div>
        <div className="help-column">
          <h4>Quick actions</h4>
          <ul className="quick-actions">
            <li>
              <a href="/upload">Upload files</a>
            </li>
            <li>
              <a href="/files">Browse files</a>
            </li>
            <li>
              Tip: Use "My Data Only" to restrict answers to your uploads.
            </li>
            <li>
              Tip: Click a source link to jump to the exact page or timestamp.
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
