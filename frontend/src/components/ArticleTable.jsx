import { Link } from "react-router-dom";
import { formatDateTime } from "../articles";
import StatusBadge from "./StatusBadge";

// Used by the Articles page and by a section's page.
// showSection is off on a section's page, where every row has the same section.
// When selectedIds and onToggle are given (editors on the Articles page),
// each row gets a checkbox for bulk actions.
export default function ArticleTable({ articles, showSection, selectedIds, onToggle, onToggleAll }) {
  const selectable = selectedIds !== undefined;

  let allSelected = articles.length > 0;
  if (selectable) {
    for (const article of articles) {
      if (!selectedIds.has(article.id)) {
        allSelected = false;
      }
    }
  }

  return (
    <table className="table">
      <thead>
        <tr>
          {selectable && (
            <th className="check-cell">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={() => onToggleAll(!allSelected)}
                aria-label="Select all on this page"
                title="Select all on this page"
              />
            </th>
          )}
          <th>Title</th>
          {showSection && <th>Section</th>}
          <th>Author</th>
          <th>Status</th>
          <th>Publish time</th>
          <th>Last updated</th>
        </tr>
      </thead>
      <tbody>
        {articles.map((article) => (
          <tr key={article.id} className={selectable && selectedIds.has(article.id) ? "selected" : ""}>
            {selectable && (
              <td className="check-cell">
                <input
                  type="checkbox"
                  checked={selectedIds.has(article.id)}
                  onChange={() => onToggle(article.id)}
                  aria-label={"Select " + article.title}
                />
              </td>
            )}
            <td>
              <Link to={"/articles/" + article.id}>{article.title}</Link>
            </td>
            {showSection && <td>{article.section.name}</td>}
            <td>{article.author.full_name}</td>
            <td>
              <StatusBadge status={article.status} />
            </td>
            <td className="small">{formatDateTime(article.published_at || article.scheduled_for)}</td>
            <td className="small">{formatDateTime(article.updated_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
