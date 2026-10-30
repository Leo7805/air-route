import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { Brand } from "./Brand";
import { Icon } from "./Icon";

export function AppLayout() {
  const { account, logout } = useAuth();
  const isAdmin = account?.role === "Admin";
  const links = [
    { to: "/explorer", label: "Explorer", icon: "globe" as const },
    { to: "/travel-plans", label: "Travel Plans", icon: "calendar" as const },
    ...(isAdmin ? [
      { to: "/imports", label: "Data Import", icon: "upload" as const },
      { to: "/accounts", label: "Accounts", icon: "users" as const },
    ] : []),
  ];

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <aside className="sidebar">
        <NavLink className="brand-link" to="/explorer" aria-label="AirRoute home"><Brand /></NavLink>
        <div className="workspace-label">Workspace</div>
        <nav className="sidebar-nav" aria-label="Primary navigation">
          {links.map((link) => <NavLink className={({ isActive }) => isActive ? "nav-link nav-link-active" : "nav-link"} key={link.to} to={link.to}><Icon name={link.icon} />{link.label}</NavLink>)}
        </nav>
        <div className={`account-menu${isAdmin ? " account-admin" : ""}`}>
          <div className="account-profile">
            <span className="account-avatar"><Icon name={isAdmin ? "shield" : "user"} /></span>
            <div className="account-copy"><strong>{account?.username}</strong><small>{isAdmin ? "Administrator" : "User account"}</small></div>
          </div>
          <button className="button button-quiet logout-button" onClick={logout} type="button"><Icon name="logout" />Log out</button>
        </div>
      </aside>
      <main className="content" id="main-content" tabIndex={-1}><Outlet /></main>
    </div>
  );
}
