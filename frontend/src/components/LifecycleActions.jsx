import { useState } from "react";
import api, { errorMessage } from "../api";
import { useAuth } from "../AuthContext";

// The lifecycle buttons for an article or a revision ("item").
//
// Only buttons this user could use right now are shown. That is just for a
// clean screen: the server checks every rule again (lifecycle.py), and if it
// refuses, its message is shown here.
//
// props:
//   item      the article or revision (needs id and status)
//   kind      "article" or "revision" (decides the API address)
//   authorId  who wrote it: the article's author, or whoever opened the revision
//   onDone    called after a successful move, to reload the page
export default function LifecycleActions({ item, kind, authorId, onDone }) {
  const { user, isEditor } = useAuth();
  const [scheduleAt, setScheduleAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const isAuthor = user.id === authorId;
  const status = item.status;
  const thing = kind === "article" ? "article" : "revision";

  const canSubmit = status === "DRAFT" && isAuthor;
  const canApprove = status === "IN_REVIEW" && isEditor && !isAuthor;
  const canSchedule = status === "APPROVED" && isEditor;
  const canPublish = status === "APPROVED" && isEditor;
  // A published revision is already part of the article, so only a scheduled one can be unpublished.
  let canUnpublish = false;
  if (isEditor) {
    if (status === "SCHEDULED") {
      canUnpublish = true;
    }
    if (status === "PUBLISHED" && kind === "article") {
      canUnpublish = true;
    }
  }

  async function move(action, data) {
    setError("");
    setBusy(true);
    let base = "/api/articles/";
    if (kind === "revision") {
      base = "/api/revisions/";
    }
    try {
      await api.post(base + item.id + "/" + action + "/", data || {});
      setScheduleAt("");
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function schedule(event) {
    event.preventDefault();
    if (scheduleAt === "") {
      setError("Pick a date and time first.");
      return;
    }
    // The picker gives local time without a zone; toISOString() sends it as UTC.
    move("schedule", { scheduled_for: new Date(scheduleAt).toISOString() });
  }

  // A short line explaining why there is nothing to click, so nobody wonders.
  let hint = "";
  if (status === "DRAFT" && !isAuthor) {
    hint = "Waiting for the author to submit this " + thing + " for review.";
  } else if (status === "IN_REVIEW" && isEditor && isAuthor) {
    hint = "You wrote this " + thing + ", so another editor must approve it.";
  } else if (status === "IN_REVIEW" && !isEditor) {
    hint = "Waiting for an editor to review it.";
  } else if (status === "APPROVED" && !isEditor) {
    hint = "Approved. An editor will schedule or publish it.";
  } else if (status === "SCHEDULED" && !isEditor) {
    hint = "Scheduled. An editor can still unpublish it.";
  }

  const nothingToDo = !canSubmit && !canApprove && !canSchedule && !canPublish && !canUnpublish;

  return (
    <div className="stack tight">
      <div className="row">
        {canSubmit && (
          <button disabled={busy} onClick={() => move("submit")}>
            Submit for review
          </button>
        )}
        {canApprove && (
          <button disabled={busy} onClick={() => move("approve")}>
            Approve
          </button>
        )}
        {canPublish && (
          <button disabled={busy} onClick={() => move("publish")}>
            Publish now
          </button>
        )}
        {canSchedule && (
          <form className="row" onSubmit={schedule}>
            <input type="datetime-local" value={scheduleAt} onChange={(e) => setScheduleAt(e.target.value)} />
            <button type="submit" className="secondary" disabled={busy}>
              Schedule
            </button>
          </form>
        )}
        {canUnpublish && (
          <button className="danger" disabled={busy} onClick={() => move("unpublish")}>
            Unpublish
          </button>
        )}
      </div>
      {nothingToDo && hint && <p className="muted small">{hint}</p>}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
