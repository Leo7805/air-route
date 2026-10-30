import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import { useAuth } from "../auth/AuthContext";
import { ApiError, api } from "../lib/api";
import type { RouteDetails, TravelPlan } from "../types/api";

type PlanFields = Pick<TravelPlan, "name" | "departure_date" | "return_date">;

const emptyFields: PlanFields = {
  name: "",
  departure_date: "",
  return_date: "",
};

function messageFor(reason: unknown, fallback: string) {
  return reason instanceof ApiError ? reason.message : fallback;
}

function routeLabel(route: RouteDetails) {
  return `${route.origin_airport?.iata_code ?? route.origin_iata ?? "Unknown"} → ${
    route.destination_airport?.iata_code ?? route.destination_iata ?? "Unknown"
  }`;
}

export function TravelPlansPage() {
  const { token } = useAuth();
  const [plans, setPlans] = useState<TravelPlan[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<TravelPlan | null>(null);
  const [fields, setFields] = useState<PlanFields>(emptyFields);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [routeId, setRouteId] = useState("");
  const [route, setRoute] = useState<RouteDetails | null>(null);
  const [isRouteLoading, setIsRouteLoading] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const listRequest = useRef(0);

  const loadPlans = useCallback(async () => {
    if (!token) return;
    const request = ++listRequest.current;
    setIsLoading(true);
    try {
      const response = await api.travelPlans(token);
      if (request !== listRequest.current) return;
      setPlans(response.items);
      setSelectedId((current) =>
        current && response.items.some((plan) => plan.plan_id === current)
          ? current
          : response.items[0]?.plan_id ?? null,
      );
    } catch (reason) {
      if (request !== listRequest.current) return;
      setFeedback({ type: "error", message: messageFor(reason, "Unable to load travel plans.") });
      setPlans([]);
      setSelectedId(null);
    } finally {
      if (request === listRequest.current) setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    setPlans([]);
    setSelectedId(null);
    setSelectedPlan(null);
    setFeedback(null);
    void loadPlans();
  }, [loadPlans]);

  useEffect(() => {
    if (!token || selectedId === null) {
      setSelectedPlan(null);
      return;
    }
    let active = true;
    api.travelPlan(token, selectedId)
      .then((plan) => {
        if (active) {
          setSelectedPlan(plan);
          setFields({
            name: plan.name,
            departure_date: plan.departure_date,
            return_date: plan.return_date,
          });
        }
      })
      .catch((reason) => {
        if (active) {
          setFeedback({ type: "error", message: messageFor(reason, "Unable to load this travel plan.") });
          setSelectedPlan(null);
        }
      })
    return () => {
      active = false;
    };
  }, [selectedId, token]);

  async function submitPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    setFeedback(null);
    setIsSubmitting(true);
    try {
      const plan = isEditing && selectedId !== null
        ? await api.updateTravelPlan(token, selectedId, fields)
        : await api.createTravelPlan(token, fields);
      setFeedback({ type: "success", message: isEditing ? "Travel plan updated." : "Travel plan created." });
      setIsEditing(false);
      setFields(emptyFields);
      await loadPlans();
      setSelectedId(plan.plan_id);
    } catch (reason) {
      setFeedback({ type: "error", message: messageFor(reason, "Unable to save travel plan.") });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function deletePlan() {
    if (!token || !selectedPlan || !window.confirm(`Delete "${selectedPlan.name}"?`)) return;
    setFeedback(null);
    setIsSubmitting(true);
    try {
      await api.deleteTravelPlan(token, selectedPlan.plan_id);
      setFeedback({ type: "success", message: "Travel plan deleted." });
      setSelectedPlan(null);
      setIsEditing(false);
      await loadPlans();
    } catch (reason) {
      setFeedback({ type: "error", message: messageFor(reason, "Unable to delete travel plan.") });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function findRoute(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    const parsedId = Number(routeId.trim());
    if (!Number.isInteger(parsedId) || parsedId < 1) {
      setFeedback({ type: "error", message: "Enter a valid positive route ID." });
      return;
    }
    setFeedback(null);
    setIsRouteLoading(true);
    setRoute(null);
    try {
      setRoute(await api.route(token, parsedId));
    } catch (reason) {
      setFeedback({ type: "error", message: messageFor(reason, "Route not found.") });
    } finally {
      setIsRouteLoading(false);
    }
  }

  async function addRoute() {
    if (!token || !selectedPlan || !route) return;
    setFeedback(null);
    setIsSubmitting(true);
    try {
      const plan = await api.addRouteToTravelPlan(token, selectedPlan.plan_id, route.route_id);
      setSelectedPlan(plan);
      setPlans((current) => current.map((item) => item.plan_id === plan.plan_id ? plan : item));
      setRoute(null);
      setRouteId("");
      setFeedback({ type: "success", message: "Route added to travel plan." });
    } catch (reason) {
      setFeedback({ type: "error", message: messageFor(reason, "Unable to add route.") });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function removeRoute(routeToRemove: number) {
    if (!token || !selectedPlan || !window.confirm("Remove this route from the plan?")) return;
    setFeedback(null);
    setIsSubmitting(true);
    try {
      await api.removeRouteFromTravelPlan(token, selectedPlan.plan_id, routeToRemove);
      const plan = await api.travelPlan(token, selectedPlan.plan_id);
      setSelectedPlan(plan);
      setPlans((current) => current.map((item) => item.plan_id === plan.plan_id ? plan : item));
      setFeedback({ type: "success", message: "Route removed from travel plan." });
    } catch (reason) {
      setFeedback({ type: "error", message: messageFor(reason, "Unable to remove route.") });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="plans-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">Travel Plans</span>
          <h1>Keep your routes together.</h1>
          <p>Private plans belong only to the currently signed-in account.</p>
        </div>
        <button className="button button-quiet" disabled={isLoading || isSubmitting} onClick={() => void loadPlans()} type="button">Refresh</button>
      </div>
      {feedback && <p className={`feedback feedback-${feedback.type}`} role="status">{feedback.message}</p>}
      <div className="plans-layout">
        <section className="panel plans-list">
          <div className="panel-heading"><div><span className="eyebrow">Your plans</span><h2>{plans.length} {plans.length === 1 ? "plan" : "plans"}</h2></div></div>
          {isLoading ? <p className="table-state">Loading travel plans…</p> :
            plans.length === 0 ? <p className="table-state">No travel plans yet.</p> :
              <div className="plan-list">{plans.map((plan) => (
                <button className={selectedId === plan.plan_id ? "plan-list-item plan-list-item-active" : "plan-list-item"} key={plan.plan_id} onClick={() => { setSelectedId(plan.plan_id); setIsEditing(false); }} type="button">
                  <strong>{plan.name}</strong>
                  <span>{plan.departure_date} → {plan.return_date}</span>
                  <small>{plan.routes.length} {plan.routes.length === 1 ? "route" : "routes"}</small>
                </button>
              ))}</div>}
          <button className="button button-primary button-wide plan-create-button" onClick={() => { setSelectedId(null); setSelectedPlan(null); setFields(emptyFields); setIsEditing(false); }} type="button">Create a new plan</button>
        </section>
        <section className="panel plan-editor">
          <div className="panel-heading"><div><span className="eyebrow">{selectedPlan && !isEditing ? "Plan details" : "Plan form"}</span><h2>{selectedPlan && !isEditing ? selectedPlan.name : isEditing ? "Edit travel plan" : "Create travel plan"}</h2></div></div>
          {selectedPlan && !isEditing ? <PlanDetails plan={selectedPlan} onEdit={() => setIsEditing(true)} onDelete={() => void deletePlan()} isSubmitting={isSubmitting} onRemoveRoute={(id) => void removeRoute(id)} token={token} /> :
            <form className="plan-form" onSubmit={submitPlan}>
              <label>Plan name<input maxLength={255} onChange={(event) => setFields({ ...fields, name: event.target.value })} required value={fields.name} /></label>
              <label>Departure date<input onChange={(event) => setFields({ ...fields, departure_date: event.target.value })} required type="date" value={fields.departure_date} /></label>
              <label>Return date<input onChange={(event) => setFields({ ...fields, return_date: event.target.value })} required type="date" value={fields.return_date} /></label>
              <div className="form-actions"><button className="button button-primary" disabled={isSubmitting} type="submit">{isSubmitting ? "Saving…" : isEditing ? "Save changes" : "Create plan"}</button>{isEditing && <button className="button button-quiet" onClick={() => setIsEditing(false)} type="button">Cancel</button>}</div>
            </form>}
        </section>
      </div>
      {selectedPlan && !isEditing && <section className="panel route-manager">
        <div className="panel-heading"><div><span className="eyebrow">Route associations</span><h2>Add an existing route</h2></div></div>
        <form className="route-lookup" onSubmit={findRoute}><label>Route ID<input inputMode="numeric" onChange={(event) => setRouteId(event.target.value)} placeholder="e.g. 1" value={routeId} /></label><button className="button button-quiet" disabled={isRouteLoading || isSubmitting} type="submit">{isRouteLoading ? "Finding…" : "Find route"}</button></form>
        {route && <div className="route-preview"><div><strong>Route {route.route_id}</strong><span>{routeLabel(route)} · {route.airline?.name ?? route.airline_iata ?? "Unknown airline"}</span></div><button className="button button-primary" disabled={isSubmitting || selectedPlan.routes.includes(route.route_id)} onClick={() => void addRoute()} type="button">{selectedPlan.routes.includes(route.route_id) ? "Already added" : "Add route"}</button></div>}
      </section>}
    </section>
  );
}

function PlanDetails({ plan, onEdit, onDelete, isSubmitting, onRemoveRoute, token }: {
  plan: TravelPlan;
  onEdit: () => void;
  onDelete: () => void;
  isSubmitting: boolean;
  onRemoveRoute: (routeId: number) => void;
  token: string | null;
}) {
  const [routes, setRoutes] = useState<RouteDetails[]>([]);
  useEffect(() => {
    let active = true;
    if (!token || plan.routes.length === 0) {
      setRoutes([]);
      return;
    }
    Promise.all(plan.routes.map((routeId) => api.route(token, routeId)))
      .then((items) => { if (active) setRoutes(items); })
      .catch(() => { if (active) setRoutes([]); });
    return () => { active = false; };
  }, [plan, token]);

  return <div className="plan-details">
    <dl className="detail-list"><dt>Departure</dt><dd>{plan.departure_date}</dd><dt>Return</dt><dd>{plan.return_date}</dd><dt>Routes</dt><dd>{plan.routes.length}</dd></dl>
    <div className="form-actions"><button className="button button-primary" disabled={isSubmitting} onClick={onEdit} type="button">Edit plan</button><button className="button button-danger" disabled={isSubmitting} onClick={onDelete} type="button">Delete plan</button></div>
    <h3>Associated routes</h3>
    {plan.routes.length === 0 ? <p className="table-state">No routes associated yet.</p> : routes.length === 0 ? <p className="table-state">Loading route details…</p> : <div className="associated-routes">{routes.map((route) => <div className="associated-route" key={route.route_id}><div><strong>{routeLabel(route)}</strong><span>{route.airline?.name ?? route.airline_iata ?? "Unknown airline"} · Route {route.route_id}</span></div><button className="text-button text-button-danger" disabled={isSubmitting} onClick={() => onRemoveRoute(route.route_id)} type="button">Remove</button></div>)}</div>}
  </div>;
}
