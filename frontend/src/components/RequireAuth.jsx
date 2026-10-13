import { Navigate } from "react-router-dom";
import { useAuth } from "../AuthContext";

// Wraps pages that need a logged-in user. This only controls what the UI shows;
// the real access rules are enforced by the API.
export default function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <p className="content">Loading…</p>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return children;
}
