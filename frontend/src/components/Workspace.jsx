import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import Chat from "./Chat.jsx";
import DocumentList from "./DocumentList.jsx";

export default function Workspace() {
  const { user, logout } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);

  useEffect(() => {
    api
      .listDocuments()
      .then(setDocuments)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

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

      <div className="layout">
        <aside className="sidebar">
          <DocumentList
            documents={documents}
            loading={loading}
            error={error}
            uploading={uploading}
            selectedIds={selectedIds}
            onUpload={handleUpload}
            onDelete={handleDelete}
            onToggle={toggleSelected}
          />
        </aside>
        <main className="main">
          <Chat selectedIds={selectedIds} readyCount={readyCount} />
        </main>
      </div>
    </div>
  );
}
