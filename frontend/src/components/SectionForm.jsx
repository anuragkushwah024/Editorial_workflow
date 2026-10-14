import { useState } from "react";

// Shared by "New section" and "Edit section". The parent decides what
// happens on submit and shows any server error it gets back.
export default function SectionForm({ initial, editors, submitLabel, onSubmit, onCancel }) {
  const [name, setName] = useState(initial.name);
  const [description, setDescription] = useState(initial.description);
  const [ownerId, setOwnerId] = useState(initial.ownerId);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      await onSubmit({ name: name, description: description, owner_id: Number(ownerId) });
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="card form" onSubmit={handleSubmit}>
      <label>
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} />
      </label>
      <label>
        Description
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
      </label>
      <label>
        Owning editor
        <select value={ownerId} onChange={(e) => setOwnerId(e.target.value)} required>
          <option value="">Choose an editor…</option>
          {editors.map((editor) => (
            <option key={editor.id} value={editor.id}>
              {editor.full_name}
            </option>
          ))}
        </select>
      </label>
      {error && <p className="error">{error}</p>}
      <div className="row">
        <button type="submit" disabled={saving}>
          {saving ? "Saving…" : submitLabel}
        </button>
        {onCancel && (
          <button type="button" className="secondary" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
