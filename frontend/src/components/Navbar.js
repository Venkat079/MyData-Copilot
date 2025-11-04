import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { isAuthenticated, clearToken, getToken } from "../utils/auth";
import "../styles/components.css";

export default function Navbar() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const logged = isAuthenticated();

  useEffect(() => {
    async function fetchUser() {
      if (!logged) return;
      try {
        const res = await fetch("http://localhost:5000/api/me", {
          headers: {
            Authorization: `Bearer ${getToken()}`,
          },
        });
        if (res.ok) {
          const data = await res.json();
          setUser(data);
        } else {
          console.warn("Failed to fetch user info");
        }
      } catch (err) {
        console.error("Error fetching user info:", err);
      }
    }
    fetchUser();
  }, [logged]);

  function handleLogout() {
    clearToken();
    setUser(null);
    navigate("/login");
  }

  return (
    <header className="nav-header">
      <div className="nav-left">
        <Link to="/dashboard" className="brand">
          MyData Copilot
        </Link>
      </div>
      <nav className="nav-right">
        {logged ? (
          <>
            <Link to="/dashboard">Dashboard</Link>
            <Link to="/upload">Upload</Link>
            <Link to="/files">Files</Link>
            <Link to="/settings">Settings</Link>

            {/* 👇 Show user name if available */}
            {user && (
              <span className="user-name">
                👋 {user.name || user.email?.split("@")[0]}
              </span>
            )}

            <button className="btn-ghost" onClick={handleLogout}>
              Logout
            </button>
          </>
        ) : (
          <>
            <Link to="/login">Login</Link>
            <Link to="/register">Register</Link>
          </>
        )}
      </nav>
    </header>
  );
}
