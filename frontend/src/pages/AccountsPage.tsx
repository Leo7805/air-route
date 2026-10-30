import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import { useAuth } from "../auth/AuthContext";
import { ApiError, api } from "../lib/api";
import type { Account } from "../types/api";

function errorMessage(reason: unknown, fallback: string) {
  return reason instanceof ApiError ? reason.message : fallback;
}

export function AccountsPage() {
  const { token } = useAuth();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isCreateOpen, setIsCreateOpen] = useState(false);

  const loadAccounts = useCallback(async () => {
    if (!token) {
      return;
    }

    setIsLoading(true);
    try {
      setAccounts(await api.accounts(token));
    } catch (reason) {
      setFeedback({
        type: "error",
        message: errorMessage(reason, "Unable to load accounts."),
      });
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void loadAccounts();
  }, [loadAccounts]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      return;
    }

    setFeedback(null);
    setIsSubmitting(true);
    try {
      await api.createAccount(token, username.trim(), password);
      setUsername("");
      setPassword("");
      setIsCreateOpen(false);
      setFeedback({ type: "success", message: "User account created." });
      await loadAccounts();
    } catch (reason) {
      setFeedback({
        type: "error",
        message: errorMessage(reason, "Unable to create the account."),
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleToggle(account: Account) {
    if (!token) {
      return;
    }

    setFeedback(null);
    setIsSubmitting(true);
    try {
      await api.updateAccountStatus(token, account.id, !account.is_active);
      setFeedback({
        type: "success",
        message: `${account.username} is now ${
          account.is_active ? "inactive" : "active"
        }.`,
      });
      await loadAccounts();
    } catch (reason) {
      setFeedback({
        type: "error",
        message: errorMessage(reason, "Unable to update the account."),
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDelete(account: Account) {
    if (!token || !window.confirm(`Delete the account "${account.username}"?`)) {
      return;
    }

    setFeedback(null);
    setIsSubmitting(true);
    try {
      await api.deleteAccount(token, account.id);
      setFeedback({ type: "success", message: "Account deleted." });
      await loadAccounts();
    } catch (reason) {
      setFeedback({
        type: "error",
        message: errorMessage(reason, "Unable to delete the account."),
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="accounts-page">
      <div className="page-heading">
        <div>
          <h1>Accounts</h1>
          <p>Only User accounts can be created, changed, or deleted.</p>
        </div>
        <div className="page-actions">
          <button className="button button-primary" onClick={() => setIsCreateOpen(true)} type="button">
            Create User
          </button>
          <button className="button button-quiet" disabled={isLoading || isSubmitting} onClick={() => void loadAccounts()} type="button">
            Refresh
          </button>
        </div>
      </div>

      {feedback && (
        <p className={`feedback feedback-${feedback.type}`} role="status">
          {feedback.message}
        </p>
      )}

      <section className="panel accounts-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Directory</span>
              <h2>All accounts</h2>
            </div>
            {!isLoading && (
              <span className="count-label">
                {accounts.length} {accounts.length === 1 ? "account" : "accounts"}
              </span>
            )}
          </div>
          {isLoading ? (
            <p className="table-state">Loading accounts…</p>
          ) : accounts.length === 0 ? (
            <p className="table-state">No accounts found.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Username</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map((account) => (
                    <tr key={account.id}>
                      <td>{account.id}</td>
                      <td className="account-name">{account.username}</td>
                      <td>{account.role}</td>
                      <td>
                        <span
                          className={
                            account.is_active
                              ? "status-badge status-active"
                              : "status-badge status-inactive"
                          }
                        >
                          {account.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td>
                        {account.role === "User" && (
                          <div className="table-actions">
                            <button
                              className="text-button"
                              disabled={isSubmitting}
                              onClick={() => void handleToggle(account)}
                              type="button"
                            >
                              {account.is_active ? "Deactivate" : "Activate"}
                            </button>
                            <button
                              className="text-button text-button-danger"
                              disabled={isSubmitting}
                              onClick={() => void handleDelete(account)}
                              type="button"
                            >
                              Delete
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </section>
      {isCreateOpen && (
        <div className="dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setIsCreateOpen(false); }}>
          <section aria-labelledby="create-user-title" aria-modal="true" className="dialog-panel" role="dialog">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">New account</span>
                <h2 id="create-user-title">Create a User</h2>
              </div>
              <button aria-label="Close create user dialog" className="button button-quiet" onClick={() => setIsCreateOpen(false)} type="button">Close</button>
            </div>
            <form onSubmit={handleCreate}>
              <label>Username<input maxLength={100} onChange={(event) => setUsername(event.target.value)} required value={username} /></label>
              <label>Password<input maxLength={128} onChange={(event) => setPassword(event.target.value)} required type="password" value={password} /></label>
              <div className="form-actions"><button className="button button-primary" disabled={isSubmitting} type="submit">{isSubmitting ? "Saving…" : "Create User"}</button><button className="button button-quiet" onClick={() => setIsCreateOpen(false)} type="button">Cancel</button></div>
            </form>
          </section>
        </div>
      )}
    </section>
  );
}
