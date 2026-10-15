import { useEffect, useState } from "react";
import api, { errorMessage } from "../api";
import { useAuth } from "../AuthContext";
import { formatDateTime } from "../articles";
import LifecycleActions from "./LifecycleActions";
import StatusBadge from "./StatusBadge";

// Changes to a published article go through a revision. The live text above
// stays as it is until the revision itself is published.
export default function RevisionPanel({ article, revisions, onChanged }) {
  const { user, isEditor } = useAuth();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  let openRevision = null;
  const published = [];
  for (const revision of revisions) {
    if (revision.status === "PUBLISHED") {
      published.push(revision);
    } else {
      openRevision = revision;
    }
  }

  const mayOpen = isEditor || article.author.id === user.id;

  async function open() {
    setError("");
    setBusy(true);
    try {
      await api.post("/api/articles/" + article.id + "/revisions/", {});
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card stack revision-panel">
      <h3>Revisions</h3>

      {openRevision === null && article.status === "PUBLISHED" && (
        <div className="stack tight">
          <p className="muted small">
            This article is live, so its text can't be edited directly. A revision goes through review on its own and
            replaces the live text only when it is published.
          </p>
          {mayOpen && (
            <div>
              <button disabled={busy} onClick={open}>
                Open revision
              </button>
            </div>
          )}
        </div>
      )}

      {openRevision !== null && <OpenRevision revision={openRevision} article={article} onChanged={onChanged} />}

      {error && <p className="error">{error}</p>}

      {published.length > 0 && (
        <ul className="plain-list small">
          {published.map((revision) => (
            <li key={revision.id}>
              <span>
                Revision {revision.number} by {revision.created_by.full_name}
              </span>
              <span className="muted">published {formatDateTime(revision.published_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function OpenRevision({ revision, article, onChanged }) {
  const { user, isEditor } = useAuth();
  const [title, setTitle] = useState(revision.title);
  const [body, setBody] = useState(revision.body);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  // When the revision changes (after a move or a save), show its latest text.
  useEffect(() => {
    setTitle(revision.title);
    setBody(revision.body);
  }, [revision.id, revision.title, revision.body]);

  const mayEdit = isEditor || revision.created_by.id === user.id;
  const signedOff = revision.status === "APPROVED" || revision.status === "SCHEDULED";

  async function save(event) {
    event.preventDefault();
    setError("");
    setSaved(false);
    setSaving(true);
    try {
      await api.patch("/api/revisions/" + revision.id + "/", { title: title, body: body });
      setSaved(true);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="stack">
      <div className="row small">
        <strong>Revision {revision.number}</strong>
        <StatusBadge status={revision.status} />
        <span className="muted">opened by {revision.created_by.full_name}</span>
        {revision.scheduled_for && <span className="muted">· goes live {formatDateTime(revision.scheduled_for)}</span>}
      </div>

      {article.status !== "PUBLISHED" && (
        <p className="notice">The article is not published right now, so this revision can't go live until it is.</p>
      )}

      {mayEdit ? (
        <form className="stack tight" onSubmit={save}>
          {signedOff && (
            <p className="notice">Saving changes will send this revision back to In Review.</p>
          )}
          <label>
            Title
            <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={255} />
          </label>
          <label>
            Body
            <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={8} required />
          </label>
          <div className="row">
            <button type="submit" className="secondary" disabled={saving}>
              {saving ? "Saving…" : "Save revision"}
            </button>
            {saved && <span className="muted small">Saved.</span>}
          </div>
          {error && <p className="error">{error}</p>}
        </form>
      ) : (
        <div className="stack tight">
          <strong>{revision.title}</strong>
          <div className="article-body">{revision.body}</div>
        </div>
      )}

      <LifecycleActions item={revision} kind="revision" authorId={revision.created_by.id} onDone={onChanged} />
    </div>
  );
}
