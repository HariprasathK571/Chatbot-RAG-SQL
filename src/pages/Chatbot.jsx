import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { authFetch } from "../utils/authFetch";
import { clearTokens } from "../utils/authService";

// ✅ API Base URL from env
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const API_URL = `${API_BASE_URL}/api/chatbot/query_stream`;

export default function Chatbot() {
  const nav = useNavigate();

  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState("");

  // ✅ auto-scroll logic
  const chatWindowRef = useRef(null);
  const bottomRef = useRef(null);
  const [autoScroll, setAutoScroll] = useState(true);

  const userEmail = useMemo(() => localStorage.getItem("userEmail"), []);

  // ✅ detect if user scrolled away from bottom
  useEffect(() => {
    const el = chatWindowRef.current;
    if (!el) return;

    const handleScroll = () => {
      const threshold = 120; // px from bottom
      const atBottom =
        el.scrollHeight - el.scrollTop - el.clientHeight < threshold;

      setAutoScroll(atBottom);
    };

    el.addEventListener("scroll", handleScroll);
    return () => el.removeEventListener("scroll", handleScroll);
  }, []);

  // ✅ scroll ONLY if autoScroll enabled
  useEffect(() => {
    if (!autoScroll) return;
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, autoScroll]);

  // ✅ logout helper (only called when refresh also fails)
  const logout = () => {
    clearTokens();
    nav("/login");
  };

  const clearChat = () => {
    setMessages([]);
    setError("");
    setQuestion("");
  };

  const runQueryStream = async () => {
    setError("");

    const q = question.trim();
    if (!q) {
      setError("Please enter a question");
      return;
    }

    // ✅ Add user msg
    const userMsg = {
      id: crypto.randomUUID(),
      role: "user",
      content: q,
    };

    // ✅ assistant placeholder
    const botMsgId = crypto.randomUUID();
    const botMsg = {
      id: botMsgId,
      role: "assistant",
      content: "",
      mode: "sql",
    };

    setAutoScroll(true);
    setMessages((prev) => [...prev, userMsg, botMsg]);
    setQuestion("");
    setStreaming(true);

    try {
      // ✅ IMPORTANT CHANGE: use authFetch instead of normal fetch
      // This automatically refreshes access token if expired
      const res = await authFetch(
        API_URL,
        {
          method: "POST",
          body: JSON.stringify({ question: q }),
        },
        () => {
          // ✅ only runs if BOTH tokens expired
          logout();
        }
      );

      if (!res.ok) {
        throw new Error(`API error: ${res.status}`);
      }

      if (!res.body) {
        throw new Error("No response body (stream not supported?)");
      }

      // ✅ stream reading (same logic as before)
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // ✅ backend sends JSON per line
        let lines = buffer.split("\n");
        buffer = lines.pop(); // keep incomplete line

        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            const data = JSON.parse(line);

            if (data.chunk) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === botMsgId
                    ? { ...m, content: m.content + data.chunk }
                    : m
                )
              );
            }

            if (data.error) {
              setError(data.error);
            }
          } catch {
            // ignore invalid json
          }
        }
      }
    } catch (e) {
      setError("Failed to connect to API: " + e.message);
    } finally {
      setStreaming(false);
    }
  };

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    setAutoScroll(true);
  };

  const handleKeyDown = (e) => {
    // ✅ Enter = send, Shift+Enter = new line
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!streaming) runQueryStream();
    }
  };

  return (
    <div className="chatLayout">
      {/* ✅ Sidebar */}
      <aside className="sidebar">
        <div className="brandSide">
          <div className="logo">DS</div>
          <div>
            <h2>DataSage</h2>
            <p className="muted small">{userEmail || "User"}</p>
          </div>
        </div>

        <button className="btnSecondary" onClick={clearChat}>
          + New Chat
        </button>

        <div className="sideHint">
          <p className="muted small">
            Ask anything about your data.
            <br />
            SQL will stream live.
          </p>
        </div>

        <button className="btnDanger" onClick={logout}>
          Logout
        </button>
      </aside>

      {/* ✅ Main */}
      <main className="chatMain">
        <header className="topbar">
          <div>
            <h3>Chatbot</h3>
            <p className="muted small">Streaming Mode</p>
          </div>

          {streaming && <span className="badge">Generating...</span>}
        </header>

        {/* ✅ Chat Window */}
        <section className="chatWindow" ref={chatWindowRef}>
          {messages.length === 0 ? (
            <div className="emptyState">
              <h2>👋 Welcome to DataSage</h2>
              <p className="muted">
                Type a question like:
                <br />
                <b>“Show top 10 customers by loan amount”</b>
              </p>
            </div>
          ) : (
            messages.map((m) => <MessageBubble key={m.id} msg={m} />)
          )}

          {!autoScroll && (
            <button className="scrollDownBtn" onClick={scrollToBottom}>
              ↓ New Messages
            </button>
          )}

          <div ref={bottomRef} />
        </section>

        {/* ✅ Error */}
        {error && <div className="errorBar">{error}</div>}

        {/* ✅ Input */}
        <footer className="chatInputBar">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter your question... (Enter to send, Shift+Enter new line)"
            rows={2}
          />

          <button
            className="btnPrimary"
            disabled={streaming}
            onClick={runQueryStream}
          >
            {streaming ? "Running..." : "Run Query"}
          </button>
        </footer>
      </main>
    </div>
  );
}

function MessageBubble({ msg }) {
  const isUser = msg.role === "user";

  return (
    <div className={`bubbleRow ${isUser ? "right" : "left"}`}>
      <div className={`bubble ${isUser ? "userBubble" : "botBubble"}`}>
        {isUser ? (
          <div className="bubbleText">{msg.content}</div>
        ) : (
          <pre className="codeBlock">
            <code>{msg.content || "..."}</code>
          </pre>
        )}
      </div>
    </div>
  );
}
