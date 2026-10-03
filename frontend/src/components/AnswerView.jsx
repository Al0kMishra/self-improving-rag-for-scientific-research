const MARKER = /(\[\d+(?:\s*[,;]\s*\d+)*\])/g;

function numbersIn(token) {
  return token
    .slice(1, -1)
    .split(/\s*[,;]\s*/)
    .map(Number);
}

function Paragraph({ text, activeMarker, onHover, onSelect }) {
  return (
    <p>
      {text.split(MARKER).map((token, index) => {
        if (index % 2 === 0) return <span key={index}>{token}</span>;
        return numbersIn(token).map((number) => (
          <button
            key={`${index}-${number}`}
            type="button"
            className={number === activeMarker ? "cite active" : "cite"}
            onMouseEnter={() => onHover(number)}
            onMouseLeave={() => onHover(null)}
            onFocus={() => onHover(number)}
            onBlur={() => onHover(null)}
            onClick={() => onSelect(number)}
            aria-label={`Show evidence ${number}`}
          >
            {number}
          </button>
        ));
      })}
    </p>
  );
}

export default function AnswerView({ result, activeMarker, onHover, onSelect, children }) {
  const paragraphs = (result.answer || "").split(/\n+/).filter(Boolean);
  const notes = [];
  if (result.invalid_citations.length) {
    notes.push(`Removed citations to evidence that does not exist: ${result.invalid_citations.join(", ")}`);
  }
  if (result.uncited_claims) {
    notes.push(`${result.uncited_claims} of ${result.total_claims} sentences carry no citation`);
  }

  return (
    <section className="card answer">
      <div className="answer-head">
        <h2 className="headline-sm">Answer</h2>
        <span className="chip">{result.mode === "proposed" ? "Self-improving" : "Baseline"}</span>
      </div>
      {result.insufficient_evidence && (
        <div className="notice" role="note">
          <strong>Evidence is insufficient.</strong>{" "}
          {result.missing_information || "The retrieved excerpts only partly answer this question."}
        </div>
      )}
      <div className="answer-text">
        {paragraphs.map((text, index) => (
          <Paragraph key={index} text={text} activeMarker={activeMarker} onHover={onHover} onSelect={onSelect} />
        ))}
      </div>
      {notes.length > 0 && (
        <ul className="body-sm muted answer-notes">
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
      <div className="answer-foot body-sm muted">
        {result.llm_model && <span>Model {result.llm_model}</span>}
        {result.keywords.length > 0 && <span>Keywords: {result.keywords.join(", ")}</span>}
      </div>
      {children}
    </section>
  );
}
