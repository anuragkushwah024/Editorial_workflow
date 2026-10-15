import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api, { errorMessage } from "../api";
import { useAuth } from "../AuthContext";
import { canEditArticle, formatDateTime } from "../articles";
import LifecycleActions from "../components/LifecycleActions";
import RevisionPanel from "../components/RevisionPanel";
import StatusBadge from "../components/StatusBadge";
import Timeline from "../components/Timeline";

// One article: its live content, the lifecycle buttons, revisions and the timeline.
export default function ArticlePage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [article, setArticle] = useState(null);
  const [revisions, setRevisions] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState("");

  // After any change (a move, a save, a comment) everything is reloaded from
  // the server, so the page never shows a guess about the new state.
  const load = useCallback(() => {
    Promise.all([
      api.get("/api/articles/" + id + "/"),
      api.get("/api/articles/" + id + "/revisions/"),
      api.get("/api/articles/" + id + "/timeline/"),
    ])
      .then(([articleResponse, revisionsResponse, timelineResponse]) => {
        setArticle(articleResponse.data);
        setRevisions(revisionsResponse.data);
        setTimeline(timelineResponse.data);
      })
      .catch((err) => {
        if (err.response && err.response.status === 404) {
          setNotFound(true);
        } else {
          setError(errorMessage(err));
        }
      });
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

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

  // The revision panel is only useful once the article has been published.
  const showRevisions = article.status === "PUBLISHED" || revisions.length > 0;

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
        <LifecycleActions item={article} kind="article" authorId={article.author.id} onDone={load} />
      </div>

      {showRevisions && <RevisionPanel article={article} revisions={revisions} onChanged={load} />}

      <Timeline articleId={article.id} entries={timeline} onCommented={load} />
    </div>
  );
}
