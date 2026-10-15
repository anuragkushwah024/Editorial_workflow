import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errorMessage } from "../api";
import { useAuth } from "../AuthContext";
import ArticleTable from "../components/ArticleTable";

// Every article the logged-in user can see. The server decides what that is
// (editors: all; writers: their sections), so this page just shows the result.
// Search, filters, sorting and pages come in Phase 4.
export default function ArticlesPage() {
  const { isEditor } = useAuth();
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/api/articles/")
      .then((response) => setArticles(response.data))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  let emptyText = "No articles yet. Write the first one.";
  if (!isEditor) {
    emptyText = "No articles in your sections yet.";
  }

  return (
    <div className="stack">
      <div className="page-head">
        <h2>Articles</h2>
        <Link to="/articles/new" className="button">
          New article
        </Link>
      </div>

      {error && <p className="error">{error}</p>}

      {loading ? (
        <p className="muted">Loading…</p>
      ) : articles.length === 0 ? (
        <p className="card muted">{emptyText}</p>
      ) : (
        <ArticleTable articles={articles} showSection={true} />
      )}
    </div>
  );
}
