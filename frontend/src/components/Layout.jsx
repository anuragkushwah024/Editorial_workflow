import { NavLink, Outlet } from "react-router-dom";
import { AlertsProvider, useAlerts } from "../AlertsContext";
import { useAuth } from "../AuthContext";

// The "Alerts" link with the overdue count (goal 10).
function AlertsLink() {
  const { count } = useAlerts();
  return (
    <NavLink to="/alerts">
      Alerts
      {count > 0 && (
        <span className="nav-badge" aria-label={count + " overdue"}>
          {count}
        </span>
      )}
    </NavLink>
  );
}

export default function Layout() {
  return (
    <AlertsProvider>
      <LayoutInner />
    </AlertsProvider>
  );
}

function LayoutInner() {
  const { user, logout, isEditor } = useAuth();
  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">Newsroom</span>
        <nav>
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/articles">Articles</NavLink>
          <NavLink to="/sections">{isEditor ? "Sections" : "My sections"}</NavLink>
          <AlertsLink />
        </nav>
        <div className="user-box">
          <span>
            {user.full_name} <span className="role-tag">{user.role}</span>
          </span>
          <button className="link-button" onClick={logout}>
            Log out
          </button>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
