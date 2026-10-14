import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../AuthContext";

export default function Layout() {
  const { user, logout, isEditor } = useAuth();
  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">Newsroom</span>
        <nav>
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/sections">{isEditor ? "Sections" : "My sections"}</NavLink>
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
