import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export default function Register() {
  const nav = useNavigate();
  const REGISTER_URL = useMemo(() => `${API_BASE_URL}/api/auth/register`, []);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [success, setSuccess] = useState("");

  const handleRegister = async (e) => {
    e.preventDefault();
    setErr("");
    setSuccess("");

    if (!fullName.trim() || !email.trim() || !password.trim()) {
      setErr("All fields are required");
      return;
    }

    try {
      setLoading(true);

      const res = await fetch(REGISTER_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: fullName.trim(),
          email: email.trim(),
          password,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || "Register failed");
      }

      setSuccess("Registration successful. Redirecting to login...");
      setTimeout(() => nav("/login"), 1200);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="loginCard">
        <div className="brand">
          <div className="logo">DS</div>
          <div>
            <h1>Create Account</h1>
            <p className="muted">Register to access DataSage</p>
          </div>
        </div>

        <form onSubmit={handleRegister} className="form">
          <label>Full Name</label>
          <input
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Your name"
            type="text"
          />

          <label>Email</label>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="example@email.com"
            type="email"
          />

          <label>Password</label>
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            type="password"
          />

          {err && <div className="errorBox">{err}</div>}
          {success && <div className="successBox">{success}</div>}

          <button className="btnPrimary" disabled={loading}>
            {loading ? "Creating..." : "Register"}
          </button>

          <p className="muted small" style={{ textAlign: "center" }}>
            Already have account?{" "}
            <span className="linkBtn" onClick={() => nav("/login")}>
              Login
            </span>
          </p>
        </form>
      </div>
    </div>
  );
}
