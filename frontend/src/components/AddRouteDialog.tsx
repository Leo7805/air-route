import { useLayoutEffect, useRef } from "react";
import type { RouteSummary, TravelPlan } from "../types/api";

/** Uses native modal focus handling while keeping plan selection and actions in the page. */
export function AddRouteDialog({ route, plans, isLoading, isAdding, message, targetPlanId, onTargetPlanChange, onConfirm, onClose }: {
  route: RouteSummary;
  plans: TravelPlan[];
  isLoading: boolean;
  isAdding: boolean;
  message: string;
  targetPlanId: number | null;
  onTargetPlanChange: (id: number) => void;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  // Native modality traps focus; close before removal so focus returns to the opener.
  useLayoutEffect(() => {
    const element = dialog.current;
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    element?.showModal();
    return () => { element?.close(); trigger?.focus({ preventScroll: true }); };
  }, []);

  return <dialog aria-labelledby="add-route-title" aria-describedby="add-route-description" className="dialog-panel add-route-dialog" ref={dialog}
    onCancel={(event) => { event.preventDefault(); if (!isAdding) onClose(); }}
    onClick={(event) => { if (event.target === event.currentTarget && !isAdding) {
      const bounds = event.currentTarget.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) onClose();
    } }}>
    <h2 id="add-route-title">Add Route #{route.route_id}</h2>
    <p className="muted" id="add-route-description">Select the travel plan to which this route will be added.</p>
    <form onSubmit={(event) => { event.preventDefault(); onConfirm(); }}>
      {isLoading ? <p className="table-state" role="status">Loading your plans…</p> : plans.length > 0 ? <label>Travel Plan
        <select disabled={isAdding} onChange={(event) => onTargetPlanChange(Number(event.target.value))} value={targetPlanId ?? ""}>
          {plans.map((plan) => <option key={plan.plan_id} value={plan.plan_id}>{plan.name}{plan.routes.includes(route.route_id) ? " (already added)" : ""}</option>)}
        </select>
      </label> : null}
      {message && <p className="feedback feedback-error" role="alert">{message}</p>}
      <div className="form-actions"><button className="button button-quiet" disabled={isAdding} onClick={onClose} type="button">Cancel</button>
        <button className="button button-primary" disabled={isLoading || isAdding || targetPlanId === null || !plans.some((plan) => plan.plan_id === targetPlanId && !plan.routes.includes(route.route_id))} type="submit">{isAdding ? "Adding…" : "Add Route"}</button></div>
    </form>
  </dialog>;
}
