import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import api, { errorMessage } from "../api";
import { useAuth } from "../AuthContext";
import { canEditArticle } from "../articles";

// /articles/new            create (optionally ?section=ID to preselect a section)
// /articles/:id/edit       edit title and body
export default function ArticleFormPage() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, isEditor } = useAuth();
  const isNew = id === undefined;

  const [sections, setSections] = useState([]);
  const [article, setArticle] = useState(null);
  const [sectionId, setSectionId] = useState(searchParams.get("section") || "");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isNew) {
      // The server only returns sections this user may use: an editor gets
      // every active section, a writer only the ones they are assigned to.
      api
        .get("/api/sections/")
        .then((response) => setSections(response.data))
        .catch((err) => setError(errorMessage(err)))
        .finally(() => setLoading(false));
    } else {
      api
        .get("/api/articles/" + id + "/")
        .then((response) => {
          setArticle(response.data);
          setTitle(response.data.title);
          setBody(response.data.body);
        })
        .catch((err) => setError(errorMessage(err)))
        .finally(() => setLoading(false));
    }
  }, [id, isNew]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      let response;
      if (isNew) {
        response = await api.post("/api/articles/", { section_id: Number(sectionId), title: title, body: body });
      } else {
        response = await api.patch("/api/articles/" + id + "/", { title: title, body: body });
      }
      navigate("/articles/" + response.data.id);
    } catch (err) {
      // Whatever the server refused, show its own explanation.
      setError(errorMessage(err));
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="muted">Loading…</p>;
  }

  if (!isNew && !article) {
    return (
      <div className="card stack">
        <p className="error">{error || "This article does not exist, or you can't see it."}</p>
        <Link to="/articles">Back to articles</Link>
      </div>
    );
  }

  if (isNew && sections.length === 0) {
    return (
      <div className="card stack">
        <p>
          {isEditor
            ? "There are no active sections yet. Create a section first."
            : "You are not assigned to any section yet, so you can't write an article. Ask an editor to add you."}
        </p>
        <Link to="/articles">Back to articles</Link>
      </div>
    );
  }

  if (!isNew && !canEditArticle(user, article)) {
    let reason = "You can only edit articles you wrote.";
    if (article.status === "PUBLISHED") {
      reason = "This article is published, so it can't be edited directly. Open a revision from the article page instead.";
    }
    return (
      <div className="card stack">
        <p>{reason}</p>
        <Link to={"/articles/" + article.id}>Back to the article</Link>
      </div>
    );
  }

  let backLink = "/articles";
  if (!isNew) {
    backLink = "/articles/" + article.id;
  }

  return (
    <div className="stack">
      <Link to={backLink} className="small">
        ← Back
      </Link>
      <form className="card form wide" onSubmit={handleSubmit}>
        <h2>{isNew ? "New article" : "Edit article"}</h2>

        {!isNew && (article.status === "APPROVED" || article.status === "SCHEDULED") && (
          <p className="notice">
            This article is {article.status === "APPROVED" ? "approved" : "scheduled"}. Saving changes will send
            it back to In Review{article.status === "SCHEDULED" ? " and remove its publish time" : ""}.
          </p>
        )}

        {isNew && (
          <label>
            Section
            <select value={sectionId} onChange={(e) => setSectionId(e.target.value)} required>
              <option value="">Choose a section…</option>
              {sections.map((section) => (
                <option key={section.id} value={section.id}>
                  {section.name}
                </option>
              ))}
            </select>
          </label>
        )}
        {!isNew && <p className="muted small">Section: {article.section.name}</p>}

        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={255} />
        </label>
        <label>
          Body
          <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={14} required />
        </label>

        {error && <p className="error">{error}</p>}

        <div className="row">
          <button type="submit" disabled={saving}>
            {saving ? "Saving…" : isNew ? "Create draft" : "Save changes"}
          </button>
          <Link to={backLink} className="button secondary">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
