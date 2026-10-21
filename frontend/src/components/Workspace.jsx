import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import Chat from "./Chat.jsx";
import ConversationList from "./ConversationList.jsx";
import DocumentList from "./DocumentList.jsx";

export default function Workspace() {
  const { user, logout } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);

  useEffect(() => {
    api
      .listConversations()
      .then(setConversations)
      .catch(() => {
        // Not critical: the chat still works without the list
      });
  }, []);

  useEffect(() => {
    api
      .listDocuments()
      .then(setDocuments)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const hasActiveJobs = documents.some(
    (d) => d.status === "pending" || d.status === "processing"
  );

  // While anything is queued or processing, refresh the list every 2 seconds
  useEffect(() => {
    if (!hasActiveJobs) return;
    const timer = setInterval(async () => {
      try {
        setDocuments(await api.listDocuments());
      } catch {
        // Ignore one failed check; the next one will try again
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [hasActiveJobs]);

  async function handleUpload(file) {
    setError("");
    setUploading(true);
    try {
      const document = await api.uploadDocument(file);
      setDocuments((prev) => [document, ...prev]);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(document) {
    if (!window.confirm(`Delete "${document.title}"? This can't be undone.`)) return;
    setError("");
    try {
      await api.deleteDocument(document.id);
      setDocuments((prev) => prev.filter((d) => d.id !== document.id));
      setSelectedIds((prev) => prev.filter((id) => id !== document.id));
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleRetry(document) {
    setError("");
    try {
      const updated = await api.reprocessDocument(document.id);
      setDocuments((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
    } catch (err) {
      setError(err.message);
    }
  }

  function handleConversationSaved(conversation, makeActive) {
    // Move this chat to the top of the list (or add it if it's new)
    setConversations((prev) => [
      conversation,
      ...prev.filter((c) => c.id !== conversation.id),
    ]);
    if (makeActive) setActiveConversationId(conversation.id);
  }

  async function handleDeleteConversation(conversation) {
    if (!window.confirm(`Delete the chat "${conversation.title}"?`)) return;
    setError("");
    try {
      await api.deleteConversation(conversation.id);
      setConversations((prev) => prev.filter((c) => c.id !== conversation.id));
      if (activeConversationId === conversation.id) setActiveConversationId(null);
    } catch (err) {
      setError(err.message);
    }
  }

  function toggleSelected(id) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  const readyCount = documents.filter((d) => d.status === "ready").length;

  return (
    <div className="app">
      <header className="topbar">
        <span className="logo">DocuMind</span>
        <div className="topbar-right">
          <span className="muted">{user.username}</span>
          <button className="btn-secondary" onClick={logout}>
            Log out
          </button>
        </div>
      </header>

      {user.is_demo && (
        <div className="demo-banner">
          You're using the shared demo account. Ask anything about the sample documents.
          Create your own account to upload PDFs. Demo chats are visible to other visitors.
        </div>
      )}

      <div className="layout">
        <aside className="sidebar">
          <DocumentList
            readOnly={user.is_demo}
            documents={documents}
            loading={loading}
            error={error}
            uploading={uploading}
            selectedIds={selectedIds}
            onUpload={handleUpload}
            onDelete={handleDelete}
            onRetry={handleRetry}
            onToggle={toggleSelected}
          />
          <hr className="sidebar-divider" />
          <ConversationList
            conversations={conversations}
            activeId={activeConversationId}
            onSelect={setActiveConversationId}
            onNew={() => setActiveConversationId(null)}
            onDelete={handleDeleteConversation}
          />
        </aside>
        <main className="main">
          <Chat
            conversationId={activeConversationId}
            selectedIds={selectedIds}
            readyCount={readyCount}
            onConversationSaved={handleConversationSaved}
          />
        </main>
      </div>
    </div>
  );
}
