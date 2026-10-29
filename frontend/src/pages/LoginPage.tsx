import { FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../lib/api";

export function LoginPage() {
  const { isAuthenticated, isLoading, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isLoading && isAuthenticated) {
    return <Navigate to="/explorer" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      await login(username.trim(), password);
      const from = (location.state as { from?: { pathname: string } } | null)
        ?.from?.pathname;
      navigate(from ?? "/explorer", { replace: true });
    } catch (reason) {
      setError(
        reason instanceof ApiError ? reason.message : "Unable to sign in.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-visual">
        <div>
          <span className="eyebrow">Airline route explorer</span>
          <h1>Plan routes with a clearer view of the network.</h1>
          <p>
            Explore imported aviation data and keep private travel plans in one
            calm workspace.
          </p>
        </div>
        <div className="route-line" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </section>
      <section className="auth-panel">
        <div className="auth-card">
          <span className="brand-mark">AR</span>
          <span className="eyebrow">Welcome back</span>
          <h2>Sign in to AirRoute</h2>
          <p className="muted">Use your existing AirRoute account.</p>
          <form onSubmit={handleSubmit}>
            <label>
              Username
              <input
                autoComplete="username"
                onChange={(event) => setUsername(event.target.value)}
                required
                value={username}
              />
            </label>
            <label>
              Password
              <input
                autoComplete="current-password"
                onChange={(event) => setPassword(event.target.value)}
                required
                type="password"
                value={password}
              />
            </label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="button button-primary button-wide" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}
