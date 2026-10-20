import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import Message from "./Message.jsx";

export default function Chat({ selectedIds, readyCount }) {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, asking]);

  async function handleSubmit(event) {
    event?.preventDefault();
    const text = question.trim();
    if (!text || asking) return;

    setMessages((prev) => [...prev, { role: "user", text }]);
    setQuestion("");
    setAsking(true);

    try {
      const result = await api.ask(text, selectedIds);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: result.answer, sources: result.sources },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: err.message, sources: [], isError: true },
      ]);
    } finally {
      setAsking(false);
    }
  }

  function handleKeyDown(event) {
    // Enter sends, Shift+Enter makes a new line
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  }

  const noDocuments = readyCount === 0;

  return (
    <div className="chat">
      <div className="messages">
        {messages.length === 0 && (
          <div className="empty-chat">
            <h2>Ask your documents anything</h2>
            <p className="muted">
              {noDocuments
                ? "Upload a PDF on the left to get started."
                : "Every answer cites the page it came from. Click a number to see the exact passage."}
            </p>
          </div>
        )}

        {messages.map((message, index) => (
          <Message key={index} message={message} />
        ))}

        {asking && (
          <div className="message assistant">
            <div className="bubble typing">Searching your documents…</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form className="composer" onSubmit={handleSubmit}>
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={noDocuments ? "Upload a document first" : "Ask a question…"}
          rows={2}
          maxLength={1000}
          disabled={noDocuments}
        />
        <button
          className="btn-primary"
          type="submit"
          disabled={noDocuments || asking || !question.trim()}
        >
          Ask
        </button>
      </form>
    </div>
  );
}
