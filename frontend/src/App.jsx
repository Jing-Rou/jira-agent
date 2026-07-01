import { useEffect, useRef, useState } from "react";
import { Bot, Clock3, Loader2, MessageSquareText, RefreshCcw, Send, Server, Sparkles, UserRound } from "lucide-react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

function apiUrl(path) {
  return `${API_BASE_URL}${path}`;
}

const suggestions = [
  "Triage SCRUM-5",
  "Triage SCRUM-10",
  "Check related tickets for SCRUM-12",
  "Generate acceptance criteria for SCRUM-7",
];

function parseRecords(payload) {
  if (!payload?.result) return [];
  if (Array.isArray(payload.result)) return payload.result;

  try {
    return JSON.parse(payload.result.replaceAll("'", '"'));
  } catch {
    return [{ ticket_key: "Raw", request: "Records response", response: payload.result }];
  }
}

function nowLabel() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function App() {
  const [health, setHealth] = useState("checking");
  const [records, setRecords] = useState([]);
  const [message, setMessage] = useState("Triage SCRUM-5");
  const [messages, setMessages] = useState([
    {
      id: crypto.randomUUID(),
      role: "assistant",
      text: "Hi, I can run your Jira triage agent. Send a request with a ticket key like SCRUM-5.",
      time: nowLabel(),
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [recordsLoading, setRecordsLoading] = useState(false);
  const scrollRef = useRef(null);
  const [pendingDraft, setPendingDraft] = useState(null);

  async function checkHealth() {
    try {
      const response = await fetch(apiUrl("/triage/health-check/"));
      const data = await response.json();
      setHealth(response.ok ? data.message ?? "ONLINE" : "error");
    } catch {
      setHealth("offline");
    }
  }

  async function loadRecords() {
    setRecordsLoading(true);
    try {
      const response = await fetch(apiUrl("/triage/get-records/"));
      const data = await response.json();
      setRecords(parseRecords(data));
    } catch {
      setRecords([]);
    } finally {
      setRecordsLoading(false);
    }
  }

  async function sendMessage(event) {
    // stops the browser's default behavior of refreshing the whole page when a form is submitted
    event?.preventDefault();
    const trimmed = message.trim();
    //  If the box is empty, or if a request is already in progress, it stops here and does nothing
    if (!trimmed || loading) return;

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      text: trimmed,
      time: nowLabel(),
    };

    setMessages((current) => [...current, userMessage]);
    setMessage("");
    setLoading(true);

    try {
      const response = await fetch(apiUrl("/triage/jira-agent/"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request: trimmed }),
      });
      const data = await response.json();

      if (response.ok && data.type === "issue_draft") {
        // store the draft, don't treat it as a finished message
        setPendingDraft(data.draft);

        setMessages((current) => [
          ...current,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            text: data.output,
            time: nowLabel(),
            draft: data.draft,   // attach the draft to this specific message
          },
        ]);
      } else {
        const assistantText = response.ok
          ? data.output || "Task completed."
          : data.error || data.request?.[0] || "The agent could not complete that request.";

        setMessages((current) => [
          ...current,
          { id: crypto.randomUUID(), 
            role: "assistant", 
            text: assistantText, 
            time: nowLabel(), 
            error: !response.ok },
        ]);

        if (response.ok) await loadRecords();
      }
    } catch (err) {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: err.message || "Could not reach the Django API.",
          time: nowLabel(),
          error: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function confirmCreateIssue(draft) {
    setLoading(true);
    try {
      const response = await fetch(apiUrl("/triage/triage-jira-ticket/"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      const data = await response.json();

      const assistantText = response.ok
        ? data.output || `Created ${data.ticket_key}.`
        : data.error || "Could not create the issue.";

      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), 
          role: "assistant", 
          text: assistantText, 
          time: nowLabel(), 
          error: !response.ok },
      ]);

      setPendingDraft(null);
      if (response.ok) await loadRecords();
    } catch (err) {
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "assistant", text: err.message || "Could not reach the Django API.", time: nowLabel(), error: true },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function cancelDraft() {
    setPendingDraft(null);
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), 
        role: "assistant", 
        text: "Okay, I won't create that ticket.", 
        time: nowLabel() },
    ]);
  }

  function useSuggestion(text) {
    setMessage(text);
  }

  useEffect(() => {
    checkHealth();
    loadRecords();
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  return (
    <main className="app-shell">
      <section className="chat-layout">
        <aside className="side-panel">
          <div className="brand-row">
            <div className="brand-icon"><Bot size={24} /></div>
            <div>
              <p className="eyebrow">Jira Agent</p>
              <h1>Chatbot</h1>
            </div>
          </div>

          <div className="api-card">
            <div>
              <p className="muted">Backend</p>
              <div className="api-status"><Server size={17} /> Django API</div>
            </div>
            <span className={`health health-${health.toLowerCase()}`}>{health}</span>
            <button type="button" onClick={checkHealth} title="Refresh API status" aria-label="Refresh API status">
              <RefreshCcw size={16} />
            </button>
          </div>

          <div className="suggestions">
            <p className="section-title">Try asking</p>
            {suggestions.map((item) => (
              <button type="button" key={item} onClick={() => useSuggestion(item)}>
                <Sparkles size={15} />
                <span>{item}</span>
              </button>
            ))}
          </div>

          <div className="history-card">
            <div className="history-header">
              <p className="section-title">Recent runs</p>
              <button type="button" onClick={loadRecords} title="Refresh history" aria-label="Refresh history">
                {recordsLoading ? <Loader2 className="spin" size={15} /> : <RefreshCcw size={15} />}
              </button>
            </div>
            <div className="history-list">
              {records.length === 0 ? (
                <p className="empty-history">No saved records yet.</p>
              ) : (
                records.slice(0, 6).map((record, index) => (
                  <article key={`${record.ticket_key || "record"}-${record.created_at || index}`}>
                    <strong>{record.ticket_key || "Record"}</strong>
                    <span>{record.request}</span>
                  </article>
                ))
              )}
            </div>
          </div>
        </aside>

        <section className="chat-panel">
          <header className="chat-header">
            <div>
              <p className="eyebrow">Conversation</p>
              <h2>Ask the Jira triage agent</h2>
            </div>
            <div className="mode-pill"><MessageSquareText size={16} /> Live API</div>
          </header>

          <div className="messages" aria-live="polite">
            {messages.map((item) => (
              <div className={`message-row ${item.role}`} key={item.id}>
                <div className="avatar" aria-hidden="true">
                  {item.role === "assistant" ? <Bot size={18} /> : <UserRound size={18} />}
                </div>
                <div className={`bubble ${item.error ? "error" : ""}`}>
                  <div className="bubble-meta">
                    <span>{item.role === "assistant" ? "Jira Agent" : "You"}</span>
                    <time><Clock3 size={12} /> {item.time}</time>
                  </div>
                  <pre>{item.text}</pre>
                    {item.draft && (
                    <div className="draft-preview">
                      <p><strong>Summary:</strong> {item.draft.summary}</p>
                      <p><strong>Type:</strong> {item.draft.work_type}</p>
                      <p><strong>Description:</strong> {item.draft.description}</p>

                      {pendingDraft === item.draft && (
                        <div className="draft-actions">
                          <button type="button" onClick={() => confirmCreateIssue(item.draft)} disabled={loading}>
                            Confirm & Create
                          </button>
                          <button type="button" onClick={cancelDraft} disabled={loading}>
                            Cancel
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="message-row assistant">
                <div className="avatar" aria-hidden="true"><Bot size={18} /></div>
                <div className="bubble typing">
                  <Loader2 className="spin" size={18} />
                  <span>Running Jira triage...</span>
                </div>
              </div>
            )}
            <div ref={scrollRef} />
          </div>

          <form className="composer" onSubmit={sendMessage}>
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="Ask something like: Triage SCRUM-5"
              rows={2}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  sendMessage();
                }
              }}
            />
            <button type="submit" disabled={loading || !message.trim()} aria-label="Send message" title="Send message">
              {loading ? <Loader2 className="spin" size={20} /> : <Send size={20} />}
            </button>
          </form>
        </section>
      </section>
    </main>
  );
}