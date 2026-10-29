import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/AppLayout";
import { AdminRoute } from "./components/AdminRoute";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AccountsPage } from "./pages/AccountsPage";
import { LoginPage } from "./pages/LoginPage";
import { ExplorerPage } from "./pages/ExplorerPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";

export function App() {
  return (
    <Routes>
      <Route element={<LoginPage />} path="/login" />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route element={<ExplorerPage />} path="/explorer" />
          <Route element={<PlaceholderPage />} path="/travel-plans" />
          <Route element={<AdminRoute />}>
            <Route element={<PlaceholderPage />} path="/imports" />
            <Route element={<AccountsPage />} path="/accounts" />
          </Route>
        </Route>
      </Route>
      <Route element={<Navigate replace to="/explorer" />} path="*" />
    </Routes>
  );
}
