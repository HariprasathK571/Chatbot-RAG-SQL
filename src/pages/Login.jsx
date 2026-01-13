import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

/**
 * ✅ Configure API Base URL here
 * In production, use .env:
 * VITE_API_BASE_URL=http://127.0.0.1:8000
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export default function Login() {
  const nav = useNavigate();

  const LOGIN_URL = useMemo(() => `${API_BASE_URL}/api/auth/login`, []);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);

  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [success, setSuccess] = useState("");

  // ✅ auto redirect if already logged in
  useEffect(() => {
    const access = localStorage.getItem("access_token");
    if (access) nav("/chat");
  }, [nav]);

  const validateInputs = () => {
    if (!email.trim()) return "Email is required";
    if (!password.trim()) return "Password is required";

    // basic email check
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return "Enter a valid email address";
    if (password.trim().length < 3) return "Password is too short";

    return "";
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setErr("");
    setSuccess("");

    const validationError = validateInputs();
    if (validationError) {
      setErr(validationError);
      return;
    }

    try {
      setLoading(true);

      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 15000); // 15 sec timeout

      const res = await fetch(LOGIN_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          password: password,
        }),
        signal: controller.signal,
      });

      clearTimeout(timeout);

      // ✅ Handle non-200 errors from FastAPI
      if (!res.ok) {
        let msg = "Login failed";
        try {
          const data = await res.json();
          msg = data?.detail || msg;
        } catch {
          // ignore json parse fail
        }
        throw new Error(msg);
      }

      const data = await res.json();

      if (!data?.access_token || !data?.refresh_token) {
        throw new Error("Invalid server response: token missing");
      }

      // ✅ Store tokens
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);

      // optional: store email
      localStorage.setItem("userEmail", email.trim());

      setSuccess("Login successful. Redirecting...");
      nav("/chat");
    } catch (error) {
      if (error.name === "AbortError") {
        setErr("Request timeout. Please try again.");
      } else {
        setErr(error.message || "Login failed");
      }
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
            <p className="muted">Login to access chatbot</p>
          </div>
        </div>

        <form onSubmit={handleLogin} className="form">
          <label>Email</label>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="example@email.com"
            type="email"
            autoComplete="email"
          />

          <label>Password</label>
          <div style={{ position: "relative" }}>
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              style={{ paddingRight: "44px" }}
            />

            <button
              type="button"
              onClick={() => setShowPassword((s) => !s)}
              className="btnEye"
              aria-label="Toggle password visibility"
              title={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? "🙈" : "👁️"}
            </button>
          </div>

          {/* ✅ errors */}
          {err && <div className="errorBox">{err}</div>}
          {success && <div className="successBox">{success}</div>}

          <button className="btnPrimary" disabled={loading}>
            {loading ? "Signing in..." : "Login"}
          </button>

          {/* ✅ Useful links section */}
          <div className="loginFooter">
            <p className="muted small">
              Don’t have an account?{" "}
              <span
                className="linkBtn"
                onClick={() => nav("/register")}
                role="button"
                tabIndex={0}
              >
                Register
              </span>
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}
