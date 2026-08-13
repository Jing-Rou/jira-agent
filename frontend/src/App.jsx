"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, CheckCircle2, Clock3, Lightbulb, ListChecks, Loader2, MessageSquareText, RefreshCcw, Send, Server, Sparkles, Ticket, UserRound } from "lucide-react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "";

function apiUrl(path) {
  return `${API_BASE_URL}${path}`;
}

const suggestions = [
  "Search ticket SCRUM-5",
  "How many tasks are in status to do in project SCRUM?",
  "Create a new task in project SCRUM with description 'This is a test.'",
  "Triage SCRUM-7",
];

function nowLabel() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function cleanLines(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function toBullets(text) {
  const lines = cleanLines(text);
  if (lines.length > 1) return lines.map((line) => line.replace(/^[-*]\s*/, ""));

  return text
    .split(/(?<=[.!?])\s+(?=[A-Z])/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseGeneratedComment(text) {
  const labels = ["user_stories", "acceptance_criteria", "priority", "thought"];
  const sections = {};

  labels.forEach((label, index) => {
    const start = text.indexOf(`${label}:`);
    if (start === -1) return;

    const valueStart = start + label.length + 1;
    const nextStarts = labels
      .slice(index + 1)
      .map((nextLabel) => text.indexOf(`${nextLabel}:`, valueStart))
      .filter((position) => position !== -1);
    const valueEnd = nextStarts.length ? Math.min(...nextStarts) : text.length;
    sections[label] = text.slice(valueStart, valueEnd).trim();
  });

  if (Object.keys(sections).length === 0) return null;
  return sections;
}

function normalizeOutputText(text) {
  if (typeof text === "string") {
    return text.replaceAll("\\n", "\n");
  }

  if (text?.message) {
    return text.message.replaceAll("\\n", "\n");
  }

  return String(text ?? "");
}

function parseAgentOutput(text) {
  const hasRelated = text.includes("Related tickets found:");
  const hasComment = text.includes("Generated Jira comment:");
  if (!hasRelated && !hasComment) return null;

  const [analysisText, commentText = ""] = text.split("Generated Jira comment:");
  const introText = analysisText.split("Related tickets found:")[0] || "";
  const intro = cleanLines(introText).filter((line) => !line.toLowerCase().startsWith("triage complete"));

  const related = [];
  const relatedRegex =
  /-\s*([A-Z]+-\d+)\s+\[([A-Za-z]+)\]\s+([A-Z]+-\d+)\s+(?:LLM output:|Reason)\s*([\s\S]*?)(?=\n\s*-\s*[A-Z]+-\d+\s+\[[A-Za-z]+\]\s+[A-Z]+-\d+|Generated Jira comment:|$)/g;
  let match;

  while ((match = relatedRegex.exec(analysisText)) !== null) {
    related.push({
      sourceKey: match[1],
      relationship: match[2],
      issueKey: match[3],
      thought: match[4].trim(),
    });
  }

  return {
    intro,
    related,
    comment: parseGeneratedComment(commentText),
  };
}

function TriageResult({ triage }) {
  const stories = toBullets(triage.user_stories || "");
  const criteria = toBullets(triage.acceptance_criteria || "");
  const priority = (triage.priority || "Unassigned").trim();

  return (
    <section className="triage-result">
      <header className="triage-result-header">
        <div className="triage-title">
          <span className="triage-icon"><Ticket size={17} /></span>
          <div>
            <p>Triage complete</p>
            <h3>{triage.ticket_key}</h3>
          </div>
        </div>
        <strong className={`priority-pill priority-${priority.toLowerCase()}`}>
          {priority}
        </strong>
      </header>

      {stories.length > 0 && (
        <div className="triage-block">
          <div className="triage-block-title">
            <ListChecks size={16} />
            <h4>User stories</h4>
          </div>
          <ul>
            {stories.map((story, index) => (
              <li key={`story-${index}`}>{story}</li>
            ))}
          </ul>
        </div>
      )}

      {criteria.length > 0 && (
        <div className="triage-block">
          <div className="triage-block-title">
            <CheckCircle2 size={16} />
            <h4>Acceptance criteria</h4>
          </div>
          <ul className="criteria-list">
            {criteria.map((criterion, index) => (
              <li key={`criterion-${index}`}>{criterion}</li>
            ))}
          </ul>
        </div>
      )}

      {triage.thought && (
        <div className="triage-reasoning">
          <div className="triage-block-title">
            <Lightbulb size={16} />
            <h4>Reasoning</h4>
          </div>
          <p>{triage.thought}</p>
        </div>
      )}
    </section>
  );
}

function renderInlineMarkdown(text) {
  return text
    .split(/(\*\*.*?\*\*|`.*?`)/g)
    .filter(Boolean)
    .map((part, index) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong>;
      }

      if (part.startsWith("`") && part.endsWith("`")) {
        return <code key={`${part}-${index}`}>{part.slice(1, -1)}</code>;
      }

      return part;
    });
}

function MarkdownOutput({ text }) {
  const lines = normalizeOutputText(text).split("\n");
  const blocks = [];
  let paragraph = [];
  let list = [];
  let listType = null;
  let numberCounter = 1

  function flushParagraph() {
    if (!paragraph.length) return;
    const content = paragraph.join(" ").trim();
    if (content) blocks.push({ type: "paragraph", content });
    paragraph = [];
  }

  function flushList() {
    if (!list.length) return;

    const block = { type: listType, items: list };

    if (listType === "numbers") {
      block.startAt = numberCounter;
      numberCounter += list.length;
    }

    blocks.push(block);
    list = [];
    listType = null;
  }

  lines.forEach((rawLine) => {
    const line = rawLine.trim();

    if (!line) {
      flushParagraph();
      flushList();
      return;
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    const boldHeading = line.match(/^\*\*(.+?)\*\*:?$/);
    const bullet = line.match(/^[-*•]\s+(.+)$/);
    const numbered = line.match(/^\d+[.)]\s+(.+)$/);

    if (/^-{3,}$/.test(line)) {
      flushParagraph();
      flushList();
      blocks.push({ type: "divider" });
    } else if (heading || boldHeading) {
      flushParagraph();
      flushList();
      blocks.push({
        type: "heading",
        level: heading ? heading[1].length : 3,
        content: heading ? heading[2] : boldHeading[1],
      });
    } else if (bullet || numbered) {
      flushParagraph();
      const nextType = bullet ? "bullets" : "numbers";
      if (listType && listType !== nextType) flushList();
      listType = nextType;
      list.push((bullet || numbered)[1]);
    } else {
      flushList();
      paragraph.push(line);
    }
  });

  flushParagraph();
  flushList();

  return (
    <div className="markdown-output">
      {blocks.map((block, index) => {
        if (block.type === "divider") {
          return <hr key={`divider-${index}`} />;
        }

        if (block.type === "heading") {
          const Heading = block.level <= 2 ? "h3" : "h4";
          return <Heading key={`heading-${index}`}>{renderInlineMarkdown(block.content)}</Heading>;
        }

        if (block.type === "bullets" || block.type === "numbers") {
          const List = block.type === "numbers" ? "ol" : "ul";
          const startProp = block.type === "numbers" ? { start: block.startAt } : {};
          return (
            <List key={`list-${index}`} {...startProp}>
              {block.items.map((item, itemIndex) => (
                <li key={`${item}-${itemIndex}`}>{renderInlineMarkdown(item)}</li>
              ))}
            </List>
          );
        }

        return <p key={`paragraph-${index}`}>{renderInlineMarkdown(block.content)}</p>;
      })}
    </div>
  );
}

function FormattedAgentOutput({ text, triage }) {
  if (triage) return <TriageResult triage={triage} />;

  const normalizedText = normalizeOutputText(text);
  const parsed = parseAgentOutput(normalizedText);

  if (!parsed) return <MarkdownOutput text={normalizedText} />;

  return (
    <div className="formatted-output">
      {parsed.intro.map((line) => (
        <p className="output-summary" key={line}>{line}</p>
      ))}

      {parsed.related.length > 0 && (
        <section className="output-section related-section">
          <div className="related-section-header">
            <div>
              <h3>Related issues</h3>
              <p>{parsed.related.length} matches found</p>
            </div>
          </div>

          <div className="related-list">
            {parsed.related.map((item) => (
              <article
                className="related-issue"
                key={`${item.sourceKey}-${item.issueKey}`}
              >
                <div className="related-issue-header">
                  <h4>{item.issueKey}</h4>

                  <span
                    className={`relationship-pill relationship-${item.relationship.toLowerCase()}`}
                  >
                    {item.relationship}
                  </span>
                </div>

                <p className="output-subhead">Why it matches</p>

                <ul className="related-reasons">
                  {toBullets(item.thought).map((reason, index) => (
                    <li key={`${item.issueKey}-${index}`}>{reason}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>
      )}

      {parsed.comment && (
        <section className="output-section jira-comment">
          <h2>Generated Jira comment</h2>

          {parsed.comment.user_stories && (
            <div className="comment-group">
              <h3>User stories</h3>
              <ul>
                {toBullets(parsed.comment.user_stories).map((story) => (
                  <li key={story}>{story}</li>
                ))}
              </ul>
            </div>
          )}

          {parsed.comment.acceptance_criteria && (
            <div className="comment-group">
              <h3>Acceptance criteria</h3>
              <ul>
                {toBullets(parsed.comment.acceptance_criteria).map((criteria) => (
                  <li key={criteria}>{criteria}</li>
                ))}
              </ul>
            </div>
          )}

          {parsed.comment.priority && (
            <div className="priority-row">
              <span><strong>Priority</strong></span>
              <strong className={`priority-pill priority-${parsed.comment.priority.toLowerCase()}`}>
                {parsed.comment.priority}
              </strong>
            </div>
          )}

          {parsed.comment.thought && (
            <div className="comment-group">
              <h3>LLM thought</h3>
              <ul>
                {toBullets(parsed.comment.thought).map((thought) => (
                  <li key={thought}>{thought}</li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function draftTitle(draft) {
  const titles = {
    create_issue: "Create Jira issue",
    add_comment: "Add Jira comment",
    link_issues: "Link Jira issues",
    transition_issues: "Transition Jira issues",
  };
  return titles[draft?.type] || "Confirm Jira action";
}

function DraftPreview({ draft, functionName, isPending, loading, onConfirm, onCancel }) {
  if (!draft) return null;

  return (
    <div className="draft-preview">
      <h3>{draftTitle(draft)}</h3>

      {draft.project_key && <p><strong>Project:</strong> {draft.project_key}</p>}
      {draft.ticket_key && <p><strong>Ticket:</strong> {draft.ticket_key}</p>}
      {draft.source_key && draft.target_key && (
        <p><strong>Link:</strong> {draft.source_key} -&gt; {draft.target_key} ({draft.link_type})</p>
      )}
      {draft.summary && <p><strong>Summary:</strong> {draft.summary}</p>}
      {draft.work_type && <p><strong>Type:</strong> {draft.work_type}</p>}
      {draft.description && <p><strong>Description:</strong> {draft.description}</p>}
      {draft.comment && <p><strong>Comment:</strong> {draft.comment}</p>}
      {draft.issue_keys?.length > 0 && (
        <p><strong>Issues:</strong> {draft.issue_keys.join(", ")}</p>
      )}
      {draft.from_status && draft.to_status && (
        <p><strong>Status:</strong> {draft.from_status} -&gt; {draft.to_status}</p>
      )}

      {isPending && (
        <div className="draft-actions">
          <button type="button" onClick={() => onConfirm(draft, functionName)} disabled={loading}>
            Confirm
          </button>
          <button type="button" onClick={onCancel} disabled={loading}>
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [health, setHealth] = useState("checking");
  const [message, setMessage] = useState("Triage SCRUM-5");
  const [messages, setMessages] = useState([
    {
      id: "welcome-message",
      role: "assistant",
      text: "Hi, I can run your Jira triage agent. Send a request with a ticket key like SCRUM-5.",
      time: "",
    },
  ]);
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);
  const [pendingDraft, setPendingDraft] = useState(null);
  const [threadId, setThreadId] = useState(null);

  async function checkHealth() {
    try {
      const response = await fetch(apiUrl("/triage/health-check/"));
      const data = await response.json();
      setHealth(response.ok ? data.message ?? "ONLINE" : "error");
    } catch {
      setHealth("offline");
    }
  }

  async function readApiResponse(response) {
    const text = await response.text();

    if (!text) return {};

    try {
      return JSON.parse(text);
    } catch {
      return {
        error: `${response.status} ${response.statusText}: ${text}`,
      };
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
        body: JSON.stringify({
          request: trimmed,
          ...(threadId ? { thread_id: threadId } : {}),
        }),
      });
      // const data = await response.json();
      const data = await readApiResponse(response);
      if (response.ok && data.thread_id) {
        setThreadId(data.thread_id);
      }

      if (response.ok && (data.function === "draft_issue" )) {
        // store the draft, don't treat it as a finished message
        const draft = data.draft;
        setPendingDraft(draft);

        setMessages((current) => [
          ...current,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            text: data.output,
            time: nowLabel(),
            draft,
            triage:
              data.function === "generate_triage"
                ? data.triage
                : null,
            functionName: data.function,
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
            triage:
              data.function === "generate_triage"
                ? data.triage
                : null,
            error: !response.ok },
        ]);

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

  async function confirmJiraAction(draft, functionName) {
    setLoading(true);
    const payload = {
      ...draft,
      function_name: functionName,
    };

    try {
      const response = await fetch(apiUrl("/triage/confirmed-jira-action/"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
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
          triage: response.ok && data.type === "issue_created_and_triaged" ? data.details : null,
          error: !response.ok },
      ]);

      if (response.ok) {
        setPendingDraft(null);
      }

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
        text: "Okay, I won't run that Jira action.", 
        time: nowLabel() },
    ]);
  }

  function useSuggestion(text) {
    setMessage(text);
  }

  useEffect(() => {
    setMessages((current) => current.map((item) => (
      item.id === "welcome-message" && !item.time
        ? { ...item, time: nowLabel() }
        : item
    )));
    checkHealth();
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
                  {item.role === "assistant" ? (
                    <FormattedAgentOutput text={item.text} triage={item.triage} />
                  ) : (
                    <pre>{item.text}</pre>
                  )}
                  <DraftPreview
                    draft={item.draft}
                    functionName={item.functionName}
                    isPending={pendingDraft === item.draft}
                    loading={loading}
                    onConfirm={confirmJiraAction}
                    onCancel={cancelDraft}
                  />
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
