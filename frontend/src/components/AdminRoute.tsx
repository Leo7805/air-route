import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export function AdminRoute() {
  const { account } = useAuth();

  return account?.role === "Admin" ? (
    <Outlet />
  ) : (
    <Navigate replace to="/explorer" />
  );
}
