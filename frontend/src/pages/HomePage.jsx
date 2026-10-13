import { useAuth } from "../AuthContext";

// Placeholder until the dashboard (goal 8) is built.
export default function HomePage() {
  const { user } = useAuth();
  return (
    <div>
      <h2>Welcome, {user.full_name}</h2>
      <p className="muted">You are signed in as {user.role === "EDITOR" ? "an editor" : "a writer"}.</p>
    </div>
  );
}
