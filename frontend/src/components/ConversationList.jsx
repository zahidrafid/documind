function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function ConversationList({ conversations, activeId, onSelect, onNew, onDelete }) {
  return (
    <div className="conversations">
      <div className="documents-header">
        <h2>Chats</h2>
        <button className="btn-secondary" onClick={onNew}>
          New chat
        </button>
      </div>

      {conversations.length === 0 ? (
        <p className="muted small">Your chats will appear here.</p>
      ) : (
        <ul className="conv-list">
          {conversations.map((conversation) => (
            <li
              key={conversation.id}
              className={`conv-item ${conversation.id === activeId ? "conv-active" : ""}`}
            >
              <button className="conv-main" onClick={() => onSelect(conversation.id)}>
                <span className="conv-title">{conversation.title}</span>
                <span className="conv-date">{formatDate(conversation.updated_at)}</span>
              </button>
              <button
                className="btn-icon"
                onClick={() => onDelete(conversation)}
                aria-label={`Delete chat ${conversation.title}`}
                title="Delete chat"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
