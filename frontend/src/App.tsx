import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/AppLayout";
import { AdminRoute } from "./components/AdminRoute";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AccountsPage } from "./pages/AccountsPage";
import { LoginPage } from "./pages/LoginPage";
import { ExplorerPage } from "./pages/ExplorerPage";
import { ImportPage } from "./pages/ImportPage";
import { TravelPlansPage } from "./pages/TravelPlansPage";

export function App() {
  return (
    <Routes>
      <Route element={<LoginPage />} path="/login" />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route element={<ExplorerPage />} path="/explorer" />
          <Route element={<TravelPlansPage />} path="/travel-plans" />
          <Route element={<AdminRoute />}>
            <Route element={<ImportPage />} path="/imports" />
            <Route element={<AccountsPage />} path="/accounts" />
          </Route>
        </Route>
      </Route>
      <Route element={<Navigate replace to="/explorer" />} path="*" />
    </Routes>
  );
}
