import { Link } from "react-router-dom";
import { formatDateTime } from "../articles";
import StatusBadge from "./StatusBadge";

// Used by the Articles page and by a section's page.
// showSection is off on a section's page, where every row has the same section.
export default function ArticleTable({ articles, showSection }) {
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Title</th>
          {showSection && <th>Section</th>}
          <th>Author</th>
          <th>Status</th>
          <th>Last updated</th>
        </tr>
      </thead>
      <tbody>
        {articles.map((article) => (
          <tr key={article.id}>
            <td>
              <Link to={"/articles/" + article.id}>{article.title}</Link>
            </td>
            {showSection && <td>{article.section.name}</td>}
            <td>{article.author.full_name}</td>
            <td>
              <StatusBadge status={article.status} />
            </td>
            <td className="small">{formatDateTime(article.updated_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
