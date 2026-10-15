import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api, { errorMessage } from "../api";
import { useAuth } from "../AuthContext";
import { STATUS_LABELS } from "../articles";
import ArticleTable from "../components/ArticleTable";
import BulkActionBar from "../components/BulkActionBar";

const SORT_OPTIONS = [
  { value: "", label: "Default (newest, or best match when searching)" },
  { value: "-updated", label: "Last updated: newest first" },
  { value: "updated", label: "Last updated: oldest first" },
  { value: "status", label: "Status: Draft → Published" },
  { value: "-status", label: "Status: Published → Draft" },
  { value: "publish_time", label: "Publish time: earliest first" },
  { value: "-publish_time", label: "Publish time: latest first" },
];

const FILTER_KEYS = ["q", "section", "status", "author", "sort", "page"];

// Search, filters, sorting and pages all happen on the server (goal 6).
// The current choices live in the page address (?q=...&status=...), so a
// refresh, the Back button or a copied link shows the same results.
export default function ArticlesPage() {
  const { isEditor } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [sections, setSections] = useState([]);
  const [authors, setAuthors] = useState([]);
  const [searchText, setSearchText] = useState(searchParams.get("q") || "");
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);

  // The query string as a plain object, e.g. {q: "rupee", status: "DRAFT"}.
  const params = {};
  for (const key of FILTER_KEYS) {
    const value = searchParams.get(key);
    if (value) {
      params[key] = value;
    }
  }
  const paramsKey = searchParams.toString();

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    const query = {};
    for (const key of FILTER_KEYS) {
      const value = searchParams.get(key);
      if (value) {
        query[key] = value;
      }
    }
    api
      .get("/api/articles/", { params: query })
      .then((response) => setData(response.data))
      .catch((err) => {
        setData(null);
        setError(errorMessage(err));
      })
      .finally(() => setLoading(false));
    // paramsKey changes whenever the address changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey]);

  useEffect(() => {
    load();
    setSelectedIds(new Set()); // a new search or page starts with nothing selected
  }, [load]);

  // Keep the search box in step with the address (e.g. after pressing Back).
  useEffect(() => {
    setSearchText(searchParams.get("q") || "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey]);

  // Options for the dropdowns.
  useEffect(() => {
    api.get("/api/sections/").then((response) => setSections(response.data));
    if (isEditor) {
      Promise.all([api.get("/api/auth/writers/"), api.get("/api/auth/editors/")]).then(([writers, editors]) => {
        const everyone = writers.data.concat(editors.data);
        everyone.sort((a, b) => a.full_name.localeCompare(b.full_name));
        setAuthors(everyone);
      });
    }
  }, [isEditor]);

  // Change one choice. Any change except the page itself goes back to page 1.
  function setParam(key, value) {
    const next = new URLSearchParams(searchParams);
    if (value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    if (key !== "page") {
      next.delete("page");
    }
    setSearchParams(next);
  }

  function submitSearch(event) {
    event.preventDefault();
    setParam("q", searchText.trim());
  }

  function clearAll() {
    setSearchText("");
    setSearchParams(new URLSearchParams());
  }

  function toggle(id) {
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setSelectedIds(next);
  }

  function toggleAll(select) {
    const next = new Set(selectedIds);
    for (const article of data.results) {
      if (select) {
        next.add(article.id);
      } else {
        next.delete(article.id);
      }
    }
    setSelectedIds(next);
  }

  // The CSV needs the login token, so it is fetched like any API call and
  // then handed to the browser as a file, instead of being a plain link.
  async function exportCalendar() {
    setExporting(true);
    setError("");
    try {
      const response = await api.get("/api/articles/calendar/", { responseType: "blob" });
      let filename = "editorial-calendar.csv";
      const disposition = response.headers["content-disposition"] || "";
      const match = disposition.match(/filename="([^"]+)"/);
      if (match) {
        filename = match[1];
      }
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setExporting(false);
    }
  }

  const titles = {};
  if (data) {
    for (const article of data.results) {
      titles[article.id] = article.title;
    }
  }

  const myArticles = params.author === "me";
  const hasFilters = Object.keys(params).length > 0;

  let rangeText = "";
  if (data && data.count > 0) {
    const first = (data.page - 1) * data.page_size + 1;
    const last = first + data.results.length - 1;
    rangeText = "Showing " + first + "–" + last + " of " + data.count;
  }

  return (
    <div className="stack">
      <div className="page-head">
        <h2>{myArticles ? "My articles" : "Articles"}</h2>
        <div className="row">
          <button className="secondary" onClick={exportCalendar} disabled={exporting}>
            {exporting ? "Exporting…" : "Export calendar (CSV)"}
          </button>
          <Link to="/articles/new" className="button">
            New article
          </Link>
        </div>
      </div>

      {!isEditor && (
        <div className="segmented">
          <button className={myArticles ? "" : "active"} onClick={() => setParam("author", "")}>
            All in my sections
          </button>
          <button className={myArticles ? "active" : ""} onClick={() => setParam("author", "me")}>
            My articles
          </button>
        </div>
      )}

      <div className="card filters">
        <form className="row" onSubmit={submitSearch}>
          <input
            className="search-input"
            type="search"
            placeholder="Search title and body…"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
          />
          <button type="submit">Search</button>
        </form>
        <div className="row">
          <select value={params.section || ""} onChange={(e) => setParam("section", e.target.value)}>
            <option value="">All sections</option>
            {sections.map((section) => (
              <option key={section.id} value={section.id}>
                {section.name}
              </option>
            ))}
          </select>
          <select value={params.status || ""} onChange={(e) => setParam("status", e.target.value)}>
            <option value="">All statuses</option>
            {Object.keys(STATUS_LABELS).map((status) => (
              <option key={status} value={status}>
                {STATUS_LABELS[status]}
              </option>
            ))}
          </select>
          {isEditor && (
            <select value={params.author || ""} onChange={(e) => setParam("author", e.target.value)}>
              <option value="">All authors</option>
              {authors.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.full_name}
                </option>
              ))}
            </select>
          )}
          <select value={params.sort || ""} onChange={(e) => setParam("sort", e.target.value)}>
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {hasFilters && (
            <button className="link-button" onClick={clearAll}>
              Clear all
            </button>
          )}
        </div>
      </div>

      {isEditor && (
        <BulkActionBar
          selectedIds={selectedIds}
          titles={titles}
          onDone={() => {
            setSelectedIds(new Set());
            load();
          }}
          onClear={() => setSelectedIds(new Set())}
        />
      )}

      {error && (
        <p className="error">
          {error}{" "}
          {params.page && (
            <button className="link-button" onClick={() => setParam("page", "")}>
              Go to page 1
            </button>
          )}
        </p>
      )}

      {loading && !data ? (
        <p className="muted">Loading…</p>
      ) : data && data.count === 0 ? (
        <p className="card muted">
          {hasFilters ? "No articles match these filters." : isEditor ? "No articles yet." : "No articles in your sections yet."}
        </p>
      ) : data ? (
        <div className={loading ? "stack tight loading" : "stack tight"}>
          <ArticleTable
            articles={data.results}
            showSection={true}
            selectedIds={isEditor ? selectedIds : undefined}
            onToggle={toggle}
            onToggleAll={toggleAll}
          />
          <div className="page-head small">
            <span className="muted">{rangeText}</span>
            <div className="row">
              <button
                className="secondary"
                disabled={data.page <= 1}
                onClick={() => setParam("page", String(data.page - 1))}
              >
                ← Previous
              </button>
              <span className="muted">
                Page {data.page} of {data.total_pages}
              </span>
              <button
                className="secondary"
                disabled={data.page >= data.total_pages}
                onClick={() => setParam("page", String(data.page + 1))}
              >
                Next →
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
