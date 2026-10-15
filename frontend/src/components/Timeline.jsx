import { useState } from "react";
import api, { errorMessage } from "../api";
import { formatDateTime, statusLabel } from "../articles";

// One sentence for each kind of timeline entry.
function describe(entry) {
  let about = "";
  if (entry.revision) {
    about = " revision " + entry.revision.number;
  }

  if (entry.event_type === "CREATED") {
    return "created the article";
  }
  if (entry.event_type === "EDITED") {
    const fields = (entry.payload.fields || []).join(" and ");
    return "edited the" + (about ? about + " " : " ") + fields;
  }
  if (entry.event_type === "STATUS_CHANGED") {
    let text = "moved" + (about || " it") + " from " + statusLabel(entry.from_status) + " to " + statusLabel(entry.to_status);
    if (entry.payload.scheduled_for) {
      text = text + ", publishing " + formatDateTime(entry.payload.scheduled_for);
    }
    return text;
  }
  if (entry.event_type === "REVISION_OPENED") {
    return "opened" + about;
  }
  if (entry.event_type === "REVISION_PUBLISHED") {
    return "published" + about + ", replacing the live text";
  }
  if (entry.event_type === "COMMENT") {
    return "commented";
  }
  return entry.event_type;
}

// The article's history, oldest first, plus a box to add a comment.
// There is no edit or delete anywhere here: the server has no way to do it.
export default function Timeline({ articleId, entries, onCommented }) {
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function addComment(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api.post("/api/articles/" + articleId + "/comments/", { message: comment });
      setComment("");
      onCommented();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card stack">
      <h3>Timeline</h3>
      <ol className="timeline">
        {entries.map((entry) => (
          <li key={entry.id} className={"timeline-entry type-" + entry.event_type.toLowerCase()}>
            <div className="small">
              <strong>{entry.actor.full_name}</strong> <span className="role-tag">{entry.actor_role}</span>{" "}
              {describe(entry)}
              <span className="muted"> · {formatDateTime(entry.created_at)}</span>
            </div>
            {entry.event_type === "COMMENT" && <blockquote className="comment">{entry.message}</blockquote>}
            {entry.event_type !== "COMMENT" && entry.message && <div className="muted small">{entry.message}</div>}
            {entry.event_type === "REVISION_PUBLISHED" && (
              <details className="small">
                <summary>What it said before</summary>
                <p>
                  <strong>{entry.payload.previous_title}</strong>
                </p>
                <p className="article-body">{entry.payload.previous_body}</p>
              </details>
            )}
          </li>
        ))}
      </ol>

      <form className="stack tight" onSubmit={addComment}>
        <textarea
          rows={3}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Leave a comment. Comments can't be edited or deleted later."
        />
        {error && <p className="error">{error}</p>}
        <div>
          <button type="submit" disabled={busy}>
            Add comment
          </button>
        </div>
      </form>
    </div>
  );
}
