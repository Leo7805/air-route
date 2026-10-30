import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

const links = [
  { to: "/explorer", label: "Aviation Explorer" },
  { to: "/travel-plans", label: "Travel Plans" },
];

export function AppLayout() {
  const { account, logout } = useAuth();
  const isAdmin = account?.role === "Admin";

  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink className="brand" to="/explorer">
          <span className="brand-mark">AR</span>
          <span>AirRoute</span>
        </NavLink>
        <nav className="desktop-nav" aria-label="Primary navigation">
          {links.map((link) => (
            <NavLink
              className={({ isActive }) =>
                isActive ? "nav-link nav-link-active" : "nav-link"
              }
              key={link.to}
              to={link.to}
            >
              {link.label}
            </NavLink>
          ))}
          {isAdmin && (
            <>
              <NavLink
                className={({ isActive }) =>
                  isActive ? "nav-link nav-link-active" : "nav-link"
                }
                to="/imports"
              >
                Data Import
              </NavLink>
              <NavLink
                className={({ isActive }) =>
                  isActive ? "nav-link nav-link-active" : "nav-link"
                }
                to="/accounts"
              >
                Accounts
              </NavLink>
            </>
          )}
        </nav>
        <div className="account-menu">
          <div className="account-profile">
            <span className="account-avatar" aria-hidden="true">
              {account?.username?.slice(0, 1).toUpperCase()}
            </span>
            <div className="account-copy">
              <strong>{account?.username}</strong>
              <small>{account?.role}</small>
            </div>
          </div>
          <button
            aria-label="Log out"
            className="button button-quiet logout-button"
            onClick={logout}
            type="button"
          >
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
