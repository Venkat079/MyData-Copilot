import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { post } from "../api/api";
import { saveToken } from "../utils/auth";
import "../styles/auth.css";

export default function Register() {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await post("/auth/register", { email, password, name });
      if (res.token) {
        saveToken(res.token);
        navigate("/dashboard");
      } else {
        alert(res.message || "Registration failed");
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
        <h2>Create account</h2>
        <label>Name</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
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
          {loading ? "Creating..." : "Register"}
        </button>
        <div className="auth-foot">
          <span>
            Already have an account? <Link to="/login">Login</Link>
          </span>
        </div>
      </form>
    </div>
  );
}
