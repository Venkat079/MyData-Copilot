import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { post } from "../api/api";
import { saveToken } from "../utils/auth";
import "../styles/auth.css";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      // Expect backend login at POST /auth/login -> { token }
      const res = await post("/auth/login", { email, password });
      if (res.token) {
        saveToken(res.token);
        navigate("/dashboard");
      } else {
        alert(res.message || "Missing token in response");
      }
    } catch (err) {
      console.error(err);
      alert(err.message || JSON.stringify(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-container">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h2>Login</h2>
        <label>Email</label>
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          type="email"
          required
        />
        <label>Password</label>
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          type="password"
          required
        />
        <button className="btn" type="submit" disabled={loading}>
          {loading ? "Signing in..." : "Login"}
        </button>
        <div className="auth-foot">
          <span>
            Don't have an account? <Link to="/register">Register</Link>
          </span>
        </div>
      </form>
    </div>
  );
}
