import { useState } from "react";
import { api } from "../services/api.js";

export default function FeedbackButtons({ queryId, chunkId, label, onSent, disabled }) {
  const [sent, setSent] = useState(null);
  const [error, setError] = useState(null);

  const send = async (rating) => {
    setError(null);
    try {
      await api.sendFeedback({ query_id: queryId, rating, chunk_id: chunkId ?? null });
      setSent(rating);
      onSent?.(rating);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="feedback">
      {label && <span className="body-sm muted">{label}</span>}
      <button
        type="button"
        className={sent === 1 ? "thumb chosen" : "thumb"}
        onClick={() => send(1)}
        disabled={disabled || sent !== null}
        aria-label="Helpful"
      >
        👍
      </button>
      <button
        type="button"
        className={sent === -1 ? "thumb chosen" : "thumb"}
        onClick={() => send(-1)}
        disabled={disabled || sent !== null}
        aria-label="Not helpful"
      >
        👎
      </button>
      {sent !== null && <span className="body-sm muted">Recorded</span>}
      {error && <span className="body-sm error">{error}</span>}
    </div>
  );
}
