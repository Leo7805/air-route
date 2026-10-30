import { act, StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { AuthProvider, useAuth } from "../src/auth/AuthContext";
import { AppLayout } from "../src/components/AppLayout";
import { AdminRoute } from "../src/components/AdminRoute";
import { ProtectedRoute } from "../src/components/ProtectedRoute";
import { LoginPage } from "../src/pages/LoginPage";
import { ExplorerDetails } from "../src/components/ExplorerDetails";
import { AddRouteDialog } from "../src/components/AddRouteDialog";
import type { RouteDetails, TravelPlan } from "../src/types/api";
import type { Account } from "../src/types/api";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
const key = "airroute_access_token";
const accounts: Record<string, Account> = {
  admin: { id: 1, username: "admin", role: "Admin", is_active: true },
  user: { id: 2, username: "user", role: "User", is_active: true },
};
let auth: ReturnType<typeof useAuth>;
let root: Root;
let host: HTMLDivElement;
let requestedTokens: string[] = [];
let me: (token: string) => Promise<Response>;
let authenticate: (username: string) => Promise<Response>;
const json = (body: unknown, status = 200) => Promise.resolve({
  ok: status >= 200 && status < 300,
  status, headers: new Headers({ "Content-Type": "application/json" }),
  json: async () => body,
} as Response);
function assert(value: unknown, message: string): asserts value {
  if (!value) throw new Error(message);
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
// This component is mounted only by the regression harness.
// eslint-disable-next-line react-refresh/only-export-components
function Probe() {
  auth = useAuth();
  return null;
}
async function mount(path = "/explorer") {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => root.render(
    <StrictMode><MemoryRouter initialEntries={[path]}><AuthProvider>
      <Probe />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}><Route element={<AppLayout />}>
          <Route path="/explorer" element={<div>Explorer</div>} />
          <Route element={<AdminRoute />}><Route path="/accounts" element={<div>Admin content</div>} /></Route>
        </Route></Route>
      </Routes>
    </AuthProvider></MemoryRouter></StrictMode>,
  ));
}
async function unmount() {
  await act(async () => root.unmount());
  host.remove();
}
async function login(name: string) {
  await act(async () => auth.login(name, "password"));
}
async function logout() {
  await act(async () => auth.logout());
}
function identity(name: string) {
  assert(auth.account?.username === name, "Wrong username");
  assert(auth.account.role === accounts[name].role, "Wrong role");
  assert(auth.token === name && localStorage.getItem(key) === name, "Token mismatch");
  assert(requestedTokens.at(-1) === name, "Wrong /auth/me token");
  assert(auth.isAuthenticated && !auth.isLoading, "Session not ready");
}
function signedOut() {
  assert(!auth.account && !auth.token && !auth.isAuthenticated && !auth.isLoading,
    `Session not cleared (account=${Boolean(auth.account)}, token=${Boolean(auth.token)}, loading=${auth.isLoading})`);
  assert(localStorage.getItem(key) === null, "Stored token not cleared");
}

const tests: Array<[string, () => Promise<void>]> = [
  ["Admin → User → Admin with immediate identity and navigation", async () => {
    await mount();
    for (const name of ["admin", "user", "admin"]) {
      await login(name);
      identity(name);
      assert(host.textContent?.includes("Accounts") === (name === "admin"), "Wrong admin navigation");
      assert(host.textContent?.includes(name === "admin" ? "Administrator" : "User account"), "Wrong account description");
      assert(host.querySelector(".account-avatar svg"), "Account identity has no SVG icon");
      assert(Boolean(host.querySelector(".account-admin")) === (name === "admin"), "Role icon styling did not update");
      await logout();
      signedOut();
    }
  }],
  ["Refresh restores identity and logout survives refresh", async () => {
    await mount();
    await login("user");
    await unmount();
    await mount();
    identity("user");
    await logout();
    await unmount();
    await mount();
    signedOut();
  }],
  ["Invalid and expired tokens clear the session", async () => {
    for (const status of [401, 422, 403]) {
      localStorage.setItem(key, "expired");
      me = () => json({ message: "Invalid session" }, status);
      await mount();
      signedOut();
      await unmount();
    }
    await mount();
  }],
  ["Late restoration cannot overwrite a newer login", async () => {
    localStorage.setItem(key, "admin");
    const old = deferred<Response>();
    me = (token) => token === "admin" ? old.promise : json(accounts[token]);
    await mount();
    await logout();
    await login("user");
    await act(async () => old.resolve(await json(accounts.admin)));
    identity("user");
  }],
  ["Late login success or failure cannot overwrite a newer login", async () => {
    await mount();
    for (const fail of [false, true]) {
      const old = deferred<Response>();
      me = (token) => token === "admin" ? old.promise : json(accounts[token]);
      let pending!: Promise<void>;
      await act(async () => { pending = auth.login("admin", "password").catch(() => {}); });
      await logout();
      await login("user");
      await act(async () => {
        if (fail) old.reject(new Error("Late failure"));
        else old.resolve(await json(accounts.admin));
        await pending;
      });
      identity("user");
    }
  }],
  ["Logout during /auth/me prevents session resurrection", async () => {
    await mount();
    const old = deferred<Response>();
    me = () => old.promise;
    let pending!: Promise<void>;
    await act(async () => { pending = auth.login("admin", "password"); });
    await logout();
    await act(async () => { old.resolve(await json(accounts.admin)); await pending; });
    signedOut();
  }],
  ["Late login response cannot start /auth/me for an obsolete session", async () => {
    await mount();
    const old = deferred<Response>();
    authenticate = (name) => name === "admin" ? old.promise : json({ access_token: name });
    let pending!: Promise<void>;
    await act(async () => { pending = auth.login("admin", "password"); });
    await login("user");
    await act(async () => { old.resolve(await json({ access_token: "admin" })); await pending; });
    identity("user");
    assert(!requestedTokens.includes("admin"), "Obsolete login started /auth/me");
  }],
  ["Replacement login clears old identity while validation is pending", async () => {
    await mount();
    await login("admin");
    const next = deferred<Response>();
    me = () => next.promise;
    let pending!: Promise<void>;
    await act(async () => { pending = auth.login("user", "password"); });
    assert(!auth.account && !auth.token && !auth.isAuthenticated, "Old identity retained during login");
    assert(auth.isLoading && localStorage.getItem(key) === null, "Pending session is inconsistent");
    await act(async () => { next.resolve(await json(accounts.user)); await pending; });
    identity("user");
  }],
  ["Failed replacement login clears the previous identity", async () => {
    await mount();
    await login("admin");
    me = () => json({ message: "Expired token" }, 401);
    await act(async () => {
      await auth.login("user", "password").catch(() => {});
    });
    signedOut();
  }],
  ["Unmounted login cannot restore storage", async () => {
    await mount();
    const old = deferred<Response>();
    me = () => old.promise;
    let pending!: Promise<void>;
    await act(async () => { pending = auth.login("admin", "password"); });
    await unmount();
    await act(async () => { old.resolve(await json(accounts.admin)); await pending; });
    assert(localStorage.getItem(key) === null, "Unmounted request restored storage");
    await mount();
  }],
  ["User cannot open an Admin route", async () => {
    localStorage.setItem(key, "user");
    await mount("/accounts");
    identity("user");
    assert(!host.textContent?.includes("Admin content"), "Admin route exposed");
    assert(host.textContent?.includes("Explorer"), "User not redirected");
  }],
];

const routeFixture: RouteDetails = {
  route_id: 101, airline_id: 1, airline_iata: "QF", origin_airport_id: 1,
  origin_iata: "SYD", destination_airport_id: 2, destination_iata: "MEL",
  stops: 0, codeshare: null, equipment: "737", links: { self: "/routes/101" },
  airline: null, origin_airport: null, destination_airport: null,
};
const planFixture: TravelPlan = { plan_id: 1, name: "Test plan", departure_date: "2028-01-01", return_date: "2028-01-02", routes: [] };

tests.push(
  ["Details stays non-modal, updates records, handles Escape and restores focus", async () => {
    await mount();
    const trigger = document.createElement("button");
    document.body.append(trigger);
    trigger.focus();
    let closed = 0;
    const props = { detail: routeFixture, error: "", isLoading: false, title: "Route details", trigger, modalOpen: false, onClose: () => { closed++; } };
    try {
      await act(async () => root.render(<ExplorerDetails {...props} />));
      assert(document.activeElement?.getAttribute("aria-label") === "Close details", "Drawer did not receive keyboard focus");
      assert(!document.querySelector(":modal"), "Drawer blocks the background");
      assert(document.body.style.overflow !== "hidden", "Drawer locked document scrolling");
      await act(async () => root.render(<ExplorerDetails {...props} detail={{ ...routeFixture, destination_iata: "BNE" }} modalOpen />));
      assert(host.textContent?.includes("SYD → BNE"), "Selected record did not update");
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      assert(closed === 0, "Escape leaked through the form dialog");
      await act(async () => root.render(<ExplorerDetails {...props} />));
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      assert(Number(closed) === 1, "Escape did not close details");
      await act(async () => root.render(null));
      assert(document.activeElement === trigger, "Drawer did not restore focus");
    } finally { trigger.remove(); }
  }],
  ["Add to Plan is modal, submits the selected plan and prevents duplicates", async () => {
    await mount();
    const trigger = document.createElement("button");
    document.body.append(trigger);
    trigger.focus();
    let confirmed = 0;
    const props = { route: routeFixture, plans: [planFixture], isLoading: false, isAdding: false, message: "", targetPlanId: 1, onTargetPlanChange: () => {}, onConfirm: () => { confirmed++; }, onClose: () => {} };
    await act(async () => root.render(<AddRouteDialog {...props} />));
    assert(host.querySelector("dialog")?.matches(":modal"), "Add to Plan has no modal backdrop");
    const submit = host.querySelector<HTMLButtonElement>('button[type="submit"]');
    assert(submit && !submit.disabled, "Available route could not be added");
    await act(async () => submit.click());
    assert(confirmed === 1, "Add Route did not invoke the existing action");
    await act(async () => root.render(<AddRouteDialog {...props} plans={[{ ...planFixture, routes: [routeFixture.route_id] }]} />));
    assert(submit.disabled, "Duplicate route action is enabled");
    await act(async () => root.render(<AddRouteDialog {...props} isLoading />));
    assert(submit.disabled, "Submission is enabled while plans load");
    await act(async () => root.render(null));
    assert(document.activeElement === trigger, "Modal did not restore focus");
    trigger.remove();
  }],
);

const results: string[] = [];
for (const [name, run] of tests) {
  localStorage.clear();
  requestedTokens = [];
  me = (token) => json(accounts[token]);
  authenticate = (name) => json({ access_token: name });
  globalThis.fetch = async (input, options) => {
    if (String(input).endsWith("/auth/login")) {
      const { username } = JSON.parse(String(options?.body));
      return authenticate(username);
    }
    const token = new Headers(options?.headers).get("Authorization")?.replace("Bearer ", "") ?? "";
    requestedTokens.push(token);
    // Intentionally ignore AbortSignal to exercise stale-response guards.
    return me(token);
  };
  try {
    await run();
    results.push(`PASS ${name}`);
  } catch (error) {
    results.push(`FAIL ${name}: ${error}`);
  } finally {
    await unmount();
  }
}
document.getElementById("results")!.textContent = results.join("\n");
document.documentElement.dataset.testStatus = results.some((line) => line.startsWith("FAIL")) ? "failed" : "passed";
