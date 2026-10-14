import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errorMessage } from "../api";
import { useAuth } from "../AuthContext";
import SectionForm from "../components/SectionForm";

// Editors: every section, with create and an archived view.
// Writers: "My sections", i.e. only the sections they are assigned to (goal 5).
// The filtering happens on the server; this page just shows what comes back.
export default function SectionsPage() {
  const { user, isEditor } = useAuth();
  const [sections, setSections] = useState([]);
  const [editors, setEditors] = useState([]);
  const [showArchived, setShowArchived] = useState(false);
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadSections = useCallback(() => {
    setLoading(true);
    setError("");
    const params = showArchived ? { archived: "true" } : {};
    api
      .get("/api/sections/", { params: params })
      .then((response) => setSections(response.data))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, [showArchived]);

  useEffect(() => {
    loadSections();
  }, [loadSections]);

  useEffect(() => {
    if (isEditor) {
      api.get("/api/auth/editors/").then((response) => setEditors(response.data));
    }
  }, [isEditor]);

  async function createSection(values) {
    try {
      await api.post("/api/sections/", values);
    } catch (err) {
      throw new Error(errorMessage(err));
    }
    setCreating(false);
    setShowArchived(false);
    loadSections();
  }

  return (
    <div className="stack">
      <div className="page-head">
        <h2>{isEditor ? "Sections" : "My sections"}</h2>
        {isEditor && (
          <div className="row">
            <div className="segmented">
              <button className={showArchived ? "" : "active"} onClick={() => setShowArchived(false)}>
                Active
              </button>
              <button className={showArchived ? "active" : ""} onClick={() => setShowArchived(true)}>
                Archived
              </button>
            </div>
            {!creating && <button onClick={() => setCreating(true)}>New section</button>}
          </div>
        )}
      </div>

      {creating && (
        <SectionForm
          initial={{ name: "", description: "", ownerId: String(user.id) }}
          editors={editors}
          submitLabel="Create section"
          onSubmit={createSection}
          onCancel={() => setCreating(false)}
        />
      )}

      {error && <p className="error">{error}</p>}

      {loading ? (
        <p className="muted">Loading…</p>
      ) : sections.length === 0 ? (
        <p className="card muted">
          {showArchived
            ? "No archived sections."
            : isEditor
              ? "No sections yet. Create the first one."
              : "You are not assigned to any section yet. Ask an editor to add you."}
        </p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Owner</th>
              <th>Writers</th>
              {showArchived && <th>Archived on</th>}
            </tr>
          </thead>
          <tbody>
            {sections.map((section) => (
              <tr key={section.id}>
                <td>
                  <Link to={"/sections/" + section.id}>{section.name}</Link>
                  {section.description && <div className="muted small">{section.description}</div>}
                </td>
                <td>{section.owner.full_name}</td>
                <td>{section.writer_count}</td>
                {showArchived && <td>{new Date(section.archived_at).toLocaleDateString()}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
