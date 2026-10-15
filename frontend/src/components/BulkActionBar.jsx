import { useState } from "react";
import api, { errorMessage } from "../api";
import { statusLabel } from "../articles";

// Shown to editors when articles are selected on the Articles page (goal 7).
// The server handles each article on its own and reports back per article,
// so some can succeed while others are rejected.
export default function BulkActionBar({ selectedIds, titles, onDone, onClear }) {
  const [scheduleAt, setScheduleAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  async function run(action) {
    setError("");
    setResult(null);
    const body = { action: action, ids: Array.from(selectedIds) };
    if (action === "schedule") {
      if (scheduleAt === "") {
        setError("Pick a date and time first.");
        return;
      }
      body.scheduled_for = new Date(scheduleAt).toISOString();
    }
    setBusy(true);
    try {
      const response = await api.post("/api/articles/bulk/", body);
      setResult(response.data);
      setScheduleAt("");
      onDone();
    } catch (err) {
      // A problem with the whole request (e.g. a time in the past).
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack tight">
      {selectedIds.size > 0 && (
        <div className="card bulk-bar row">
          <strong>{selectedIds.size} selected</strong>
          <input type="datetime-local" value={scheduleAt} onChange={(e) => setScheduleAt(e.target.value)} />
          <button disabled={busy} onClick={() => run("schedule")}>
            Schedule selected
          </button>
          <button className="danger" disabled={busy} onClick={() => run("unpublish")}>
            Unpublish selected
          </button>
          <button className="link-button" onClick={onClear}>
            Clear selection
          </button>
        </div>
      )}
      {error && <p className="error">{error}</p>}

      {result && (
        <div className="card stack tight">
          <div className="page-head">
            <strong>
              {result.action === "schedule" ? "Schedule" : "Unpublish"}: {result.succeeded} done, {result.rejected}{" "}
              rejected
            </strong>
            <button className="link-button" onClick={() => setResult(null)}>
              Close
            </button>
          </div>
          <ul className="plain-list small">
            {result.results.map((item) => (
              <li key={item.id}>
                <span>
                  <span className={item.ok ? "ok-mark" : "fail-mark"}>{item.ok ? "✓" : "✗"}</span>{" "}
                  {item.title || titles[item.id] || "Article #" + item.id}
                </span>
                <span className={item.ok ? "muted" : "error"}>
                  {item.ok ? "now " + statusLabel(item.status) : item.error}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
