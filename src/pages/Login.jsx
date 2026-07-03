import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export default function Login() {
  const nav = useNavigate();
  const LOGIN_URL = useMemo(() => `${API_BASE_URL}/api/auth/login`, []);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    const access = localStorage.getItem("access_token");
    if (access) nav("/chat");
  }, [nav]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setErr("");

    if (!email.trim() || !password.trim()) {
      setErr("Email and password required");
      return;
    }

    try {
      setLoading(true);

      // const res = await fetch(LOGIN_URL, {
      //   method: "POST",
      //   headers: { "Content-Type": "application/json" },
      //   body: JSON.stringify({ email: email.trim(), password }),
      // });

      const formData = new URLSearchParams();

      formData.append("username", email.trim());
      formData.append("password", password);

      const res = await fetch(LOGIN_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || "Login failed");
      }

      const data = await res.json();

      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      localStorage.setItem("userEmail", email.trim());

      nav("/chat");
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
            <h1>DataSage</h1>
            <p className="muted">Sign in to continue</p>
          </div>
        </div>

        <form onSubmit={handleLogin} className="form">
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

          <button className="btnPrimary" disabled={loading}>
            {loading ? "Signing in..." : "Login"}
          </button>

          <p className="muted small" style={{ textAlign: "center" }}>
            Don’t have an account?{" "}
            <span className="linkBtn" onClick={() => nav("/register")}>
              Register
            </span>
          </p>
        </form>
      </div>
    </div>
  );
}
