import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errorMessage } from "../api";
import { useAlerts } from "../AlertsContext";
import { useAuth } from "../AuthContext";
import { formatDateTime } from "../articles";

// "2 h 5 min late", "3 days late"...
export function howLate(minutes) {
  if (minutes < 60) {
    return minutes + " min late";
  }
  if (minutes < 60 * 24) {
    const hours = Math.floor(minutes / 60);
    const rest = minutes % 60;
    return hours + " h " + rest + " min late";
  }
  const days = Math.floor(minutes / (60 * 24));
  return days + (days === 1 ? " day late" : " days late");
}

// Overdue publish alerts (goal 10): Scheduled items whose time has passed.
export default function AlertsPage() {
  const { isEditor } = useAuth();
  const { refreshAlerts } = useAlerts();
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  const [rowErrors, setRowErrors] = useState({});
  const [busyKey, setBusyKey] = useState("");

  const load = useCallback(() => {
    api
      .get("/api/alerts/")
      .then((response) => setItems(response.data.results))
      .catch((err) => setError(errorMessage(err)));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function keyOf(item) {
    return item.kind + "-" + (item.revision_id || item.article_id);
  }

  async function act(item, request) {
    const key = keyOf(item);
    setBusyKey(key);
    setRowErrors((previous) => {
      const next = { ...previous };
      delete next[key];
      return next;
    });
    try {
      await request();
      load();
      refreshAlerts(); // the badge in the navigation
    } catch (err) {
      const message = errorMessage(err);
      setRowErrors((previous) => {
        const next = { ...previous };
        next[key] = message;
        return next;
      });
    } finally {
      setBusyKey("");
    }
  }

  function publishNow(item) {
    let url = "/api/articles/" + item.article_id + "/publish/";
    if (item.kind === "revision") {
      url = "/api/revisions/" + item.revision_id + "/publish/";
    }
    act(item, () => api.post(url));
  }

  function dismiss(item) {
    act(item, () => api.post("/api/alerts/dismiss/", { article_id: item.article_id, revision_id: item.revision_id }));
  }

  if (items === null) {
    return <p className="muted">{error || "Loading…"}</p>;
  }

  return (
    <div className="stack">
      <div className="page-head">
        <h2>Alerts</h2>
      </div>
      <p className="muted small">
        Scheduled articles whose publish time has passed but which are still not published.
        {isEditor
          ? " Publish them now, or dismiss the alert. A dismissed alert comes back if the article is scheduled again and misses its new time."
          : " An editor will publish or dismiss them."}
      </p>

      {items.length === 0 ? (
        <p className="card muted">Nothing is overdue. Everything scheduled has gone out on time.</p>
      ) : (
        <ul className="alert-list">
          {items.map((item) => {
            const key = keyOf(item);
            return (
              <li key={key} className="card alert-item">
                <div className="alert-main">
                  <div>
                    <Link to={"/articles/" + item.article_id} className="alert-title">
                      {item.title}
                    </Link>
                    {item.kind === "revision" && <span className="badge">Revision {item.revision_number}</span>}
                  </div>
                  <div className="small muted">
                    {item.section} · was due {formatDateTime(item.scheduled_for)}
                  </div>
                  <div className="late">{howLate(item.minutes_late)}</div>
                  {rowErrors[key] && <p className="error small">{rowErrors[key]}</p>}
                </div>
                {isEditor && (
                  <div className="row">
                    <button disabled={busyKey === key} onClick={() => publishNow(item)}>
                      Publish now
                    </button>
                    <button className="secondary" disabled={busyKey === key} onClick={() => dismiss(item)}>
                      Dismiss
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
