import { useRef } from "react";

export default function DocumentList({
  documents,
  loading,
  error,
  uploading,
  selectedIds,
  onUpload,
  onDelete,
  onToggle,
}) {
  const fileInput = useRef(null);

  function handleFileChange(event) {
    const file = event.target.files[0];
    if (file) onUpload(file);
    event.target.value = ""; // allows choosing the same file again
  }

  return (
    <div className="documents">
      <div className="documents-header">
        <h2>Documents</h2>
        <button
          className="btn-primary"
          onClick={() => fileInput.current.click()}
          disabled={uploading}
        >
          {uploading ? "Processing…" : "Upload PDF"}
        </button>
        <input
          ref={fileInput}
          type="file"
          accept="application/pdf,.pdf"
          hidden
          onChange={handleFileChange}
        />
      </div>

      {uploading && (
        <p className="muted small">
          Reading and indexing your PDF. Long files can take a little while.
        </p>
      )}
      {error && <p className="error">{error}</p>}

      {loading ? (
        <p className="muted">Loading…</p>
      ) : documents.length === 0 ? (
        <p className="muted">No documents yet. Upload a PDF to get started.</p>
      ) : (
        <ul className="doc-list">
          {documents.map((doc) => (
            <li key={doc.id} className="doc-item">
              <label className="doc-main">
                <input
                  type="checkbox"
                  checked={selectedIds.includes(doc.id)}
                  onChange={() => onToggle(doc.id)}
                  disabled={doc.status !== "ready"}
                />
                <span className="doc-text">
                  <span className="doc-title">{doc.title}</span>
                  {doc.status === "ready" ? (
                    <span className="doc-meta">
                      {doc.page_count} pages · {doc.chunk_count} chunks
                    </span>
                  ) : (
                    <span className={`status status-${doc.status}`}>{doc.status}</span>
                  )}
                  {doc.status === "failed" && doc.error_message && (
                    <span className="error small">{doc.error_message}</span>
                  )}
                </span>
              </label>
              <button
                className="btn-icon"
                onClick={() => onDelete(doc)}
                aria-label={`Delete ${doc.title}`}
                title="Delete"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      <p className="muted small scope-hint">
        {selectedIds.length === 0
          ? "Questions search all your documents. Tick documents to narrow the search."
          : `Questions search ${selectedIds.length} selected document${
              selectedIds.length > 1 ? "s" : ""
            }.`}
      </p>
    </div>
  );
}
