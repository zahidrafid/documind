import { useRef } from "react";

const STATUS_LABELS = {
  pending: "Queued",
  processing: "Processing…",
  failed: "Failed",
};

export default function DocumentList({
  documents,
  loading,
  error,
  uploading,
  selectedIds,
  onUpload,
  onDelete,
  onRetry,
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
          {uploading ? "Uploading…" : "Upload PDF"}
        </button>
        <input
          ref={fileInput}
          type="file"
          accept="application/pdf,.pdf"
          hidden
          onChange={handleFileChange}
        />
      </div>

      {uploading && <p className="muted small">Uploading your PDF…</p>}
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
                    <span className={`status status-${doc.status}`}>
                      {(doc.status === "pending" || doc.status === "processing") && (
                        <span className="spinner" aria-hidden="true" />
                      )}
                      {STATUS_LABELS[doc.status]}
                    </span>
                  )}
                  {doc.error_message && doc.status !== "ready" && (
                    <span className={doc.status === "failed" ? "error small" : "muted small"}>
                      {doc.error_message}
                    </span>
                  )}
                  {doc.status === "failed" && (
                    <button
                      className="btn-link small retry-btn"
                      onClick={(event) => {
                        event.preventDefault(); // don't toggle the checkbox
                        onRetry(doc);
                      }}
                    >
                      Retry
                    </button>
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
