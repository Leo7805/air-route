import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { LoginPage } from "./pages/LoginPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";

export function App() {
  return (
    <Routes>
      <Route element={<LoginPage />} path="/login" />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route element={<PlaceholderPage />} path="/explorer" />
          <Route element={<PlaceholderPage />} path="/travel-plans" />
          <Route element={<PlaceholderPage />} path="/imports" />
          <Route element={<PlaceholderPage />} path="/accounts" />
        </Route>
      </Route>
      <Route element={<Navigate replace to="/explorer" />} path="*" />
    </Routes>
  );
}
