import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { authFetch } from "../utils/authFetch";
import { clearTokens } from "../utils/authService";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export default function Chatbot() {
  const nav = useNavigate();

  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);

  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");

  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState("");

  // scroll behavior
  const chatWindowRef = useRef(null);
  const bottomRef = useRef(null);
  const [autoScroll, setAutoScroll] = useState(true);

  const userEmail = useMemo(() => localStorage.getItem("userEmail"), []);

  const logout = () => {
    clearTokens();
    nav("/login");
  };

  // ---------- API calls ----------
  const fetchConversations = async () => {
    const res = await authFetch(
      `${API_BASE_URL}/api/conversations`,
      { method: "GET" },
      logout
    );
    if (!res.ok) throw new Error(`Failed to load conversations: ${res.status}`);
    return res.json();
  };

  const fetchMessages = async (conversationId) => {
    const res = await authFetch(
      `${API_BASE_URL}/api/conversations/${conversationId}/messages`,
      { method: "GET" },
      logout
    );
    if (!res.ok) throw new Error(`Failed to load messages: ${res.status}`);
    return res.json();
  };

  const createConversation = async () => {
    const res = await authFetch(
      `${API_BASE_URL}/api/conversations`,
      { method: "POST" },
      logout
    );
    if (!res.ok) throw new Error(`Failed to create conversation: ${res.status}`);
    return res.json(); // {conversation_id, title}
  };

  // ---------- INIT ----------
  useEffect(() => {
    (async () => {
      try {
        const convos = await fetchConversations();
        setConversations(convos);

        if (convos.length > 0) {
          const id = convos[0].conversation_id;
          setActiveConversationId(id);
          const msgs = await fetchMessages(id);
          setMessages(msgs.map((m) => ({ role: m.role, content: m.content })));
        } else {
          // if none exist => create new conversation
          const newConvo = await createConversation();
          setActiveConversationId(newConvo.conversation_id);
          setMessages([]);
          const convos2 = await fetchConversations();
          setConversations(convos2);
        }
      } catch (e) {
        setError(e.message);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---------- SCROLL ----------
  useEffect(() => {
    const el = chatWindowRef.current;
    if (!el) return;

    const handleScroll = () => {
      const threshold = 120;
      const atBottom =
        el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
      setAutoScroll(atBottom);
    };

    el.addEventListener("scroll", handleScroll);
    return () => el.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    if (!autoScroll) return;
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, autoScroll]);

  // ---------- UI handlers ----------
  const handleSelectConversation = async (conversationId) => {
    try {
      setError("");
      setActiveConversationId(conversationId);
      const msgs = await fetchMessages(conversationId);
      setMessages(msgs.map((m) => ({ role: m.role, content: m.content })));
    } catch (e) {
      setError(e.message);
    }
  };

  const handleNewChat = async () => {
    try {
      setError("");
      const newConvo = await createConversation();
      setActiveConversationId(newConvo.conversation_id);
      setMessages([]);

      const convos = await fetchConversations();
      setConversations(convos);
    } catch (e) {
      setError(e.message);
    }
  };

  const sendMessage = async () => {
    setError("");

    const q = question.trim();
    if (!q) {
      setError("Please enter a question");
      return;
    }
    if (!activeConversationId) {
      setError("No active conversation. Click New Chat.");
      return;
    }

    setQuestion("");
    setAutoScroll(true);
    setStreaming(true);

    // add user msg
    setMessages((prev) => [...prev, { role: "user", content: q }]);

    // assistant placeholder
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const res = await authFetch(
        `${API_BASE_URL}/api/chatbot/query_stream`,
        {
          method: "POST",
          body: JSON.stringify({
            conversation_id: activeConversationId,
            question: q,
          }),
        },
        logout
      );

      if (!res.ok) throw new Error(`API error: ${res.status}`);
      if (!res.body) throw new Error("No stream body received");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      let buffer = "";
      let assistantText = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            const data = JSON.parse(line); // {chunk:"..."}
            if (data.chunk) {
              assistantText += data.chunk;

              setMessages((prev) => {
                const copy = [...prev];
                copy[copy.length - 1] = {
                  role: "assistant",
                  content: assistantText,
                };
                return copy;
              });
            }
          } catch {
            // ignore bad JSON
          }
        }
      }

      // refresh sidebar: title/updated_at may change after first message
      const convos = await fetchConversations();
      setConversations(convos);
    } catch (e) {
      setError("Failed: " + e.message);
    } finally {
      setStreaming(false);
    }
  };
  
  const deleteConversation = async (conversationId) => {
  try {
    setError("");

    const res = await authFetch(
      `${API_BASE_URL}/api/conversations/${conversationId}`,
      { method: "DELETE" },
      logout
    );

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data?.detail || `Delete failed: ${res.status}`);
    }

    // ✅ remove from sidebar list
    setConversations((prev) =>
      prev.filter((c) => c.conversation_id !== conversationId)
    );

    // ✅ if deleted tab was active, open next tab
    if (activeConversationId === conversationId) {
      const remaining = conversations.filter(
        (c) => c.conversation_id !== conversationId
      );

      if (remaining.length > 0) {
        const nextId = remaining[0].conversation_id;
        setActiveConversationId(nextId);

        const msgs = await fetchMessages(nextId);
        setMessages(msgs.map((m) => ({ role: m.role, content: m.content })));
      } else {
        // if none left -> create new conversation
        const newConvo = await createConversation();
        setActiveConversationId(newConvo.conversation_id);
        setMessages([]);

        const convos = await fetchConversations();
        setConversations(convos);
      }
    }
  } catch (e) {
    setError(e.message);
  }
};

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!streaming) sendMessage();
    }
  };

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    setAutoScroll(true);
  };

  return (
    <div className="chatLayout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="brandSide">
          <div className="logo">DS</div>
          <div>
            <h2>DataSage</h2>
            <p className="muted small">{userEmail || "User"}</p>
          </div>
        </div>

        <button className="btnSecondary" onClick={handleNewChat}>
          + New Chat
        </button>

        {/* Conversation Tabs */}
        <div className="tabsList">
  {conversations.map((c) => (
    <div
      key={c.conversation_id}
      className={`tabItem ${
        activeConversationId === c.conversation_id ? "activeTab" : ""
      }`}
      title={c.title}
      onClick={() => handleSelectConversation(c.conversation_id)}
    >
      <div className="tabItemRow">
        <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
          {c.title || "New Chat"}
        </span>

        {/* ✅ delete button */}
        <button
          className="tabDeleteBtn"
          title="Delete chat"
          onClick={(e) => {
            e.stopPropagation(); // ✅ prevent switching tab on delete
            const ok = window.confirm("Delete this conversation?");
            if (ok) deleteConversation(c.conversation_id);
          }}
        >
          🗑
        </button>
      </div>
    </div>
  ))}
</div>


        <button className="btnDanger" onClick={logout}>
          Logout
        </button>
      </aside>

      {/* Main */}
      <main className="chatMain">
        <header className="topbar">
          <div>
            <h3>Chatbot</h3>
            <p className="muted small">
              {activeConversationId
                ? `Conversation: ${activeConversationId}`
                : "No active conversation"}
            </p>
          </div>
          {streaming && <span className="badge">Generating...</span>}
        </header>

        <section className="chatWindow" ref={chatWindowRef}>
          {messages.length === 0 ? (
            <div className="emptyState">
              <h2>👋 Welcome to DataSage</h2>
              <p className="muted">
                Ask anything about your data.
                <br />
                Example: <b>“Show top 10 customers by loan amount”</b>
              </p>
            </div>
          ) : (
            messages.map((m, idx) => <MessageBubble key={idx} msg={m} />)
          )}

          {!autoScroll && (
            <button className="scrollDownBtn" onClick={scrollToBottom}>
              ↓ New Messages
            </button>
          )}

          <div ref={bottomRef} />
        </section>

        {error && <div className="errorBar">{error}</div>}

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
            onClick={sendMessage}
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
