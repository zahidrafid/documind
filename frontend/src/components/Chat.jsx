import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import Message from "./Message.jsx";

// Only show "Searched for" when the question was actually rewritten
function interpretedAs(searchQuery, userText) {
  if (!searchQuery || !userText) return null;
  const same = searchQuery.trim().toLowerCase() === userText.trim().toLowerCase();
  return same ? null : searchQuery;
}

function toUiMessages(apiMessages) {
  return apiMessages.map((message, index) => ({
    role: message.role,
    text: message.content,
    sources: message.sources || [],
    interpretedAs:
      message.role === "assistant"
        ? interpretedAs(message.search_query, apiMessages[index - 1]?.content)
        : null,
  }));
}

export default function Chat({ conversationId, selectedIds, readyCount, onConversationSaved }) {
  const [messages, setMessages] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const bottomRef = useRef(null);

  // Which conversation is on screen right now (read inside async code)
  const activeIdRef = useRef(conversationId);
  activeIdRef.current = conversationId;

  // Set when this component just created a conversation, so it doesn't
  // reload messages it already has
  const createdHereRef = useRef(null);

  useEffect(() => {
    if (conversationId === null) {
      setMessages([]);
      return;
    }
    if (conversationId === createdHereRef.current) {
      createdHereRef.current = null;
      return;
    }

    let cancelled = false;
    setLoadingHistory(true);
    api
      .getConversation(conversationId)
      .then((conversation) => {
        if (!cancelled) setMessages(toUiMessages(conversation.messages));
      })
      .catch((err) => {
        if (!cancelled) {
          setMessages([{ role: "assistant", text: err.message, sources: [], isError: true }]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingHistory(false);
      });

    return () => {
      cancelled = true; // ignore the response if the user switched chats
    };
  }, [conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, asking]);

  async function handleSubmit(event) {
    event?.preventDefault();
    const text = question.trim();
    if (!text || asking) return;

    const sentFrom = conversationId;
    setMessages((prev) => [...prev, { role: "user", text }]);
    setQuestion("");
    setAsking(true);

    try {
      const result = await api.ask(text, selectedIds, sentFrom);
      const stillHere = activeIdRef.current === sentFrom;

      if (stillHere) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            text: result.message.content,
            sources: result.message.sources,
            interpretedAs: interpretedAs(result.message.search_query, text),
          },
        ]);
        if (sentFrom === null) createdHereRef.current = result.conversation.id;
      }
      // Update the sidebar; only switch to the chat if the user is still on it
      onConversationSaved(result.conversation, stillHere);
    } catch (err) {
      if (activeIdRef.current === sentFrom) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", text: err.message, sources: [], isError: true },
        ]);
      }
    } finally {
      setAsking(false);
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  }

  const noDocuments = readyCount === 0;

  return (
    <div className="chat">
      <div className="messages">
        {loadingHistory && <p className="muted center-text">Loading chat…</p>}

        {!loadingHistory && messages.length === 0 && (
          <div className="empty-chat">
            <h2>Ask your documents anything</h2>
            <p className="muted">
              {noDocuments
                ? "Upload a PDF on the left to get started."
                : "Every answer cites the page it came from. You can ask follow-up questions too."}
            </p>
          </div>
        )}

        {!loadingHistory &&
          messages.map((message, index) => <Message key={index} message={message} />)}

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
