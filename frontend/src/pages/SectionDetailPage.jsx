import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api, { errorMessage } from "../api";
import { useAuth } from "../AuthContext";
import SectionForm from "../components/SectionForm";

export default function SectionDetailPage() {
  const { id } = useParams();
  const { isEditor } = useAuth();
  const [section, setSection] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [editors, setEditors] = useState([]);
  const [allWriters, setAllWriters] = useState([]);
  const [editing, setEditing] = useState(false);
  const [writerToAdd, setWriterToAdd] = useState("");
  const [error, setError] = useState("");

  const loadSection = useCallback(() => {
    api
      .get("/api/sections/" + id + "/")
      .then((response) => setSection(response.data))
      .catch((err) => {
        if (err.response && err.response.status === 404) {
          setNotFound(true);
        } else {
          setError(errorMessage(err));
        }
      });
  }, [id]);

  useEffect(() => {
    loadSection();
  }, [loadSection]);

  useEffect(() => {
    if (isEditor) {
      api.get("/api/auth/editors/").then((response) => setEditors(response.data));
      api.get("/api/auth/writers/").then((response) => setAllWriters(response.data));
    }
  }, [isEditor]);

  // Every editor action answers with the updated section, so we just show it.
  async function runAction(request) {
    setError("");
    try {
      const response = await request();
      setSection(response.data);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function saveEdit(values) {
    try {
      const response = await api.patch("/api/sections/" + id + "/", values);
      setSection(response.data);
      setEditing(false);
    } catch (err) {
      throw new Error(errorMessage(err));
    }
  }

  function assignWriter(event) {
    event.preventDefault();
    if (writerToAdd === "") {
      return;
    }
    runAction(() => api.post("/api/sections/" + id + "/writers/", { writer_id: Number(writerToAdd) }));
    setWriterToAdd("");
  }

  if (notFound) {
    return (
      <div className="card">
        <p>This section does not exist, or you are not assigned to it.</p>
        <Link to="/sections">Back to sections</Link>
      </div>
    );
  }
  if (!section) {
    return <p className="muted">{error || "Loading…"}</p>;
  }

  const assignedIds = new Set();
  for (const writer of section.writers) {
    assignedIds.add(writer.id);
  }
  const unassignedWriters = [];
  for (const writer of allWriters) {
    if (!assignedIds.has(writer.id)) {
      unassignedWriters.push(writer);
    }
  }

  return (
    <div className="stack">
      <Link to="/sections" className="small">
        ← All sections
      </Link>

      {editing ? (
        <SectionForm
          initial={{ name: section.name, description: section.description, ownerId: String(section.owner.id) }}
          editors={editors}
          submitLabel="Save changes"
          onSubmit={saveEdit}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <div className="card stack">
          <div className="page-head">
            <h2>
              {section.name} {section.is_archived && <span className="badge">Archived</span>}
            </h2>
            {isEditor && (
              <div className="row">
                <button className="secondary" onClick={() => setEditing(true)}>
                  Edit
                </button>
                {section.is_archived ? (
                  <button onClick={() => runAction(() => api.post("/api/sections/" + id + "/restore/"))}>
                    Restore
                  </button>
                ) : (
                  <button
                    className="danger"
                    onClick={() => runAction(() => api.post("/api/sections/" + id + "/archive/"))}
                  >
                    Archive
                  </button>
                )}
              </div>
            )}
          </div>
          <p>{section.description || <span className="muted">No description.</span>}</p>
          <p className="muted small">Owned by {section.owner.full_name}</p>
        </div>
      )}

      {error && <p className="error">{error}</p>}

      <div className="card stack">
        <h3>Writers ({section.writers.length})</h3>
        {section.writers.length === 0 && <p className="muted">No writers assigned yet.</p>}
        <ul className="plain-list">
          {section.writers.map((writer) => (
            <li key={writer.id}>
              <span>
                {writer.full_name} <span className="muted small">{writer.email}</span>
              </span>
              {isEditor && !section.is_archived && (
                <button
                  className="link-button"
                  onClick={() => runAction(() => api.delete("/api/sections/" + id + "/writers/" + writer.id + "/"))}
                >
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
        {isEditor && !section.is_archived && (
          <form className="row" onSubmit={assignWriter}>
            <select value={writerToAdd} onChange={(e) => setWriterToAdd(e.target.value)}>
              <option value="">Add a writer…</option>
              {unassignedWriters.map((writer) => (
                <option key={writer.id} value={writer.id}>
                  {writer.full_name}
                </option>
              ))}
            </select>
            <button type="submit" disabled={writerToAdd === ""}>
              Assign
            </button>
          </form>
        )}
        {isEditor && section.is_archived && <p className="muted small">Restore the section to change its writers.</p>}
      </div>

      <div className="card">
        <h3>Articles</h3>
        <p className="muted">Articles in this section will appear here (Session 3).</p>
      </div>
    </div>
  );
}
