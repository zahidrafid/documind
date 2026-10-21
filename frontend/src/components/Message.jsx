import { useRef, useState } from "react";

// Splits "The deadline is Friday [1][2]." into text and citation buttons
function AnswerText({ text, validNumbers, onCite }) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <p className="answer-text">
      {parts.map((part, index) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (match && validNumbers.has(Number(match[1]))) {
          const number = Number(match[1]);
          return (
            <button
              key={index}
              className="cite"
              onClick={() => onCite(number)}
              title={`Show source ${number}`}
            >
              {number}
            </button>
          );
        }
        return <span key={index}>{part}</span>;
      })}
    </p>
  );
}

export default function Message({ message }) {
  const [activeSource, setActiveSource] = useState(null);
  const sourceRefs = useRef({});

  if (message.role === "user") {
    return (
      <div className="message user">
        <div className="bubble">{message.text}</div>
      </div>
    );
  }

  const sources = message.sources || [];
  const validNumbers = new Set(sources.map((s) => s.number));

  function openSource(number) {
    setActiveSource(number);
    sourceRefs.current[number]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  return (
    <div className="message assistant">
      <div className={`bubble ${message.isError ? "bubble-error" : ""}`}>
        <AnswerText text={message.text} validNumbers={validNumbers} onCite={openSource} />

        {sources.length > 0 && (
          <div className="sources">
            <p className="sources-label">Sources</p>
            {sources.map((source) => {
              const open = activeSource === source.number;
              return (
                <div
                  key={source.number}
                  ref={(el) => {
                    sourceRefs.current[source.number] = el;
                  }}
                  className={`source ${open ? "source-open" : ""}`}
                >
                  <button
                    className="source-header"
                    onClick={() => setActiveSource(open ? null : source.number)}
                    aria-expanded={open}
                  >
                    <span className="source-number">{source.number}</span>
                    <span className="source-title">{source.title}</span>
                    <span className="source-page">page {source.page}</span>
                    <span className="source-match">{source.match}</span>
                  </button>
                  {open && <blockquote className="source-text">{source.text}</blockquote>}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
