// Small helpers shared by the article pages.

export const STATUS_LABELS = {
  DRAFT: "Draft",
  IN_REVIEW: "In Review",
  APPROVED: "Approved",
  SCHEDULED: "Scheduled",
  PUBLISHED: "Published",
};

export function statusLabel(status) {
  return STATUS_LABELS[status] || status;
}

// Mirrors the server's rule only to decide whether to SHOW the Edit button.
// The server checks it again on every request, so this is never the real guard.
export function canEditArticle(user, article) {
  if (article.status === "PUBLISHED") {
    return false; // published text changes through a revision instead
  }
  if (user.role === "EDITOR") {
    return true;
  }
  return article.author.id === user.id;
}

export function formatDateTime(value) {
  if (!value) {
    return "";
  }
  return new Date(value).toLocaleString();
}
