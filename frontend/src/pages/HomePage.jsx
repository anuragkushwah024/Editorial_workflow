import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errorMessage } from "../api";
import { useAuth } from "../AuthContext";
import StatusBadge from "../components/StatusBadge";

// The dashboard (goal 8). Every number comes from GET /api/dashboard/, which
// counts in the database and only covers articles this user can see.
// Clicking a number or a row opens the Articles page with that filter.

function shortDate(isoDate) {
  // "2026-10-12" -> "12 Oct"
  const date = new Date(isoDate + "T00:00:00");
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

function StatCard({ label, value, to, hint }) {
  return (
    <Link to={to} className="card stat-card">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
      {hint && <span className="small muted">{hint}</span>}
    </Link>
  );
}

// A plain bar chart: one series, so one colour and no legend. The number on
// each bar shows on hover (title), and this week's value is written above it.
function WeeklyChart({ weeks }) {
  let highest = 0;
  for (const week of weeks) {
    if (week.count > highest) {
      highest = week.count;
    }
  }
  const scaleTop = Math.max(highest, 1);

  return (
    <div className="chart" role="img" aria-label="Articles published per week, last 8 weeks">
      <div className="chart-plot">
        {weeks.map((week, index) => {
          const isThisWeek = index === weeks.length - 1;
          const height = (week.count / scaleTop) * 100;
          const label = "Week of " + shortDate(week.week_start) + ": " + week.count + " published";
          return (
            <div key={week.week_start} className="chart-col" title={label} aria-label={label}>
              <span className={isThisWeek ? "chart-value" : "chart-value hover-only"}>{week.count}</span>
              <div className="chart-bar" style={{ height: height + "%" }} />
            </div>
          );
        })}
      </div>
      <div className="chart-axis">
        {weeks.map((week, index) => (
          <span key={week.week_start} className="small muted">
            {index === weeks.length - 1 ? "This week" : shortDate(week.week_start)}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function HomePage() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/api/dashboard/")
      .then((response) => setData(response.data))
      .catch((err) => setError(errorMessage(err)));
  }, []);

  if (!data) {
    return <p className="muted">{error || "Loading…"}</p>;
  }

  const headline = data.headline;
  const weekText =
    "Week of " + shortDate(data.week.start.slice(0, 10)) + " (Monday to Sunday, India time)";

  let largestStatus = 1;
  for (const row of data.by_status) {
    if (row.count > largestStatus) {
      largestStatus = row.count;
    }
  }

  return (
    <div className="stack">
      <div className="page-head">
        <h2>Dashboard</h2>
        <span className="small muted">
          {user.role === "EDITOR" ? "All sections" : "Your sections"} · {weekText}
        </span>
      </div>

      <div className="stat-grid">
        <StatCard label="In review" value={headline.in_review} to="/articles?status=IN_REVIEW" />
        <StatCard
          label="Scheduled this week"
          value={headline.scheduled_this_week}
          to="/articles?status=SCHEDULED&sort=publish_time"
          hint="Opens all scheduled, soonest first"
        />
        <StatCard
          label="Published this week"
          value={headline.published_this_week}
          to="/articles?status=PUBLISHED&sort=-publish_time"
        />
        <StatCard label="Open drafts" value={headline.open_drafts} to="/articles?status=DRAFT" />
      </div>

      <div className="card stack">
        <h3>Published per week</h3>
        <WeeklyChart weeks={data.published_per_week} />
      </div>

      <div className="dashboard-columns">
        <div className="card stack">
          <h3>By status</h3>
          <ul className="plain-list breakdown">
            {data.by_status.map((row) => (
              <li key={row.status}>
                <Link to={"/articles?status=" + row.status} className="breakdown-row">
                  <StatusBadge status={row.status} />
                  <span className="breakdown-track">
                    <span className="breakdown-fill" style={{ width: (row.count / largestStatus) * 100 + "%" }} />
                  </span>
                  <span className="breakdown-count">{row.count}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <div className="card stack">
          <h3>By section</h3>
          {data.by_section.length === 0 ? (
            <p className="muted">No sections yet.</p>
          ) : (
            <table className="table compact">
              <thead>
                <tr>
                  <th>Section</th>
                  <th className="num">Draft</th>
                  <th className="num">Review</th>
                  <th className="num">Approved</th>
                  <th className="num">Sched.</th>
                  <th className="num">Published</th>
                  <th className="num">Total</th>
                </tr>
              </thead>
              <tbody>
                {data.by_section.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <Link to={"/articles?section=" + row.id}>{row.name}</Link>
                    </td>
                    <td className="num">{row.draft}</td>
                    <td className="num">{row.in_review}</td>
                    <td className="num">{row.approved}</td>
                    <td className="num">{row.scheduled}</td>
                    <td className="num">{row.published}</td>
                    <td className="num">
                      <strong>{row.total}</strong>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
