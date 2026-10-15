import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api, { errorMessage } from "../api";
import { useAuth } from "../AuthContext";
import { canEditArticle, formatDateTime } from "../articles";
import StatusBadge from "../components/StatusBadge";

// One article. For now: its content and an Edit button.
// Lifecycle buttons, revisions and the timeline are added in Phase 3, step 6.
export default function ArticlePage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [article, setArticle] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/api/articles/" + id + "/")
      .then((response) => setArticle(response.data))
      .catch((err) => {
        if (err.response && err.response.status === 404) {
          setNotFound(true);
        } else {
          setError(errorMessage(err));
        }
      });
  }, [id]);

  if (notFound) {
    return (
      <div className="card stack">
        <p>This article does not exist, or it is in a section you are not assigned to.</p>
        <Link to="/articles">Back to articles</Link>
      </div>
    );
  }
  if (!article) {
    return <p className="muted">{error || "Loading…"}</p>;
  }

  return (
    <div className="stack">
      <Link to="/articles" className="small">
        ← All articles
      </Link>

      <div className="card stack">
        <div className="page-head">
          <h2>{article.title}</h2>
          {canEditArticle(user, article) && (
            <Link to={"/articles/" + article.id + "/edit"} className="button secondary">
              Edit
            </Link>
          )}
        </div>
        <div className="row small muted">
          <StatusBadge status={article.status} />
          <span>
            in <Link to={"/sections/" + article.section.id}>{article.section.name}</Link>
          </span>
          <span>by {article.author.full_name}</span>
          <span>updated {formatDateTime(article.updated_at)}</span>
          {article.scheduled_for && <span>scheduled for {formatDateTime(article.scheduled_for)}</span>}
          {article.published_at && <span>published {formatDateTime(article.published_at)}</span>}
        </div>
        <div className="article-body">{article.body}</div>
      </div>
    </div>
  );
}
