import { statusLabel } from "../articles";

export default function StatusBadge({ status }) {
  return <span className={"status status-" + status.toLowerCase()}>{statusLabel(status)}</span>;
}
