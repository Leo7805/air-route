import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { ApiError, api } from "../lib/api";
import type {
  Airline,
  Airport,
  Page,
  RouteDetails,
  RouteSummary,
  TravelPlan,
} from "../types/api";

type Section = "airports" | "airlines" | "routes";
type RecordItem = Airport | Airline | RouteSummary;
type ExplorerNavigationState = { section?: Section; planId?: number };

const PAGE_SIZE = 12;

function messageFor(reason: unknown) {
  return reason instanceof ApiError ? reason.message : "Unable to load aviation data.";
}

function value(value: string | number | null | undefined) {
  return value === null || value === undefined || value === "" ? "—" : value;
}

export function ExplorerPage() {
  const { token } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const navigationState = location.state as ExplorerNavigationState | null;
  const [section, setSection] = useState<Section>(
    navigationState?.section === "routes" ? "routes" : "airports",
  );
  const [query, setQuery] = useState("");
  const [airportFilter, setAirportFilter] = useState("");
  const [airlineFilter, setAirlineFilter] = useState("");
  const [originFilter, setOriginFilter] = useState("");
  const [destinationFilter, setDestinationFilter] = useState("");
  const [page, setPage] = useState(0);
  const [result, setResult] = useState<Page<RecordItem> | null>(null);
  const [selected, setSelected] = useState<RecordItem | null>(null);
  const [detail, setDetail] = useState<Airport | Airline | RouteDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [plans, setPlans] = useState<TravelPlan[]>([]);
  const [pendingRoute, setPendingRoute] = useState<RouteSummary | null>(null);
  const [targetPlanId, setTargetPlanId] = useState<number | null>(
    navigationState?.planId ?? null,
  );
  const [isPlansLoading, setIsPlansLoading] = useState(false);
  const [isAddingRoute, setIsAddingRoute] = useState(false);
  const [routeActionMessage, setRouteActionMessage] = useState("");
  const requestId = useRef(0);
  const detailRequestId = useRef(0);

  const loadResults = useCallback(async () => {
    if (!token) return;
    const currentRequest = ++requestId.current;
    const controller = new AbortController();
    setIsLoading(true);
    setError("");
    try {
      let nextResult: Page<RecordItem>;
      if (section === "airports") {
        nextResult = await api.airports(token, {
          q: query.trim() || undefined,
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
        }, controller.signal);
      } else if (section === "airlines") {
        const airportId = airportFilter.trim()
          ? Number(airportFilter.trim())
          : undefined;
        nextResult = await api.airlines(token, {
          q: query.trim() || undefined,
          airportId: Number.isInteger(airportId) ? airportId : undefined,
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
        }, controller.signal);
      } else {
        const numberFilter = (input: string) => {
          const parsed = input.trim() ? Number(input.trim()) : undefined;
          return Number.isInteger(parsed) ? parsed : undefined;
        };
        nextResult = await api.routes(token, {
          airlineId: numberFilter(airlineFilter),
          originAirportId: numberFilter(originFilter),
          destinationAirportId: numberFilter(destinationFilter),
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
        }, controller.signal);
      }
      if (currentRequest === requestId.current) {
        setResult(nextResult);
      }
    } catch (reason) {
      if (!(reason instanceof DOMException && reason.name === "AbortError") &&
        currentRequest === requestId.current) {
        setError(messageFor(reason));
        setResult(null);
      }
    } finally {
      if (currentRequest === requestId.current) setIsLoading(false);
    }
    return () => controller.abort();
  }, [
    airportFilter,
    airlineFilter,
    destinationFilter,
    originFilter,
    page,
    query,
    section,
    token,
  ]);

  useEffect(() => {
    void loadResults();
  }, [loadResults]);

  useEffect(() => {
    setPage(0);
    setResult(null);
    setSelected(null);
    setDetail(null);
  }, [airportFilter, airlineFilter, destinationFilter, originFilter, query, section]);

  useEffect(() => {
    setPlans([]);
    setPendingRoute(null);
    setTargetPlanId(navigationState?.planId ?? null);
    setRouteActionMessage("");
  }, [navigationState?.planId, token]);

  async function showDetail(item: RecordItem) {
    if (!token) return;
    const currentRequest = ++detailRequestId.current;
    const controller = new AbortController();
    setSelected(item);
    setDetail(null);
    setDetailError("");
    setIsDetailLoading(true);
    try {
      const nextDetail =
        section === "airports"
          ? await api.airport(token, (item as Airport).airport_id, controller.signal)
          : section === "airlines"
            ? await api.airline(token, (item as Airline).airline_id, controller.signal)
            : await api.route(token, (item as RouteSummary).route_id, controller.signal);
      if (currentRequest === detailRequestId.current) setDetail(nextDetail);
    } catch (reason) {
      if (!(reason instanceof DOMException && reason.name === "AbortError") &&
        currentRequest === detailRequestId.current) {
        setDetailError(messageFor(reason));
      }
    } finally {
      if (currentRequest === detailRequestId.current) setIsDetailLoading(false);
    }
  }

  async function beginAddRoute(routeItem: RouteSummary) {
    if (!token) return;
    setPendingRoute(routeItem);
    setRouteActionMessage("");
    setIsPlansLoading(true);
    try {
      const response = await api.travelPlans(token);
      setPlans(response.items);
      setTargetPlanId((current) =>
        current && response.items.some((plan) => plan.plan_id === current)
          ? current
          : response.items[0]?.plan_id ?? null,
      );
      if (response.items.length === 0) {
        setRouteActionMessage("Create a travel plan before adding a route.");
      }
    } catch (reason) {
      setRouteActionMessage(messageFor(reason));
      setPlans([]);
    } finally {
      setIsPlansLoading(false);
    }
  }

  async function addRouteToPlan() {
    if (!token || !pendingRoute || targetPlanId === null) return;
    const targetPlan = plans.find((plan) => plan.plan_id === targetPlanId);
    if (!targetPlan) return;
    if (targetPlan.routes.includes(pendingRoute.route_id)) {
      setRouteActionMessage("This route is already associated with that plan.");
      return;
    }
    setIsAddingRoute(true);
    setRouteActionMessage("");
    try {
      const updatedPlan = await api.addRouteToTravelPlan(
        token,
        targetPlanId,
        pendingRoute.route_id,
      );
      setRouteActionMessage(`Route added to "${updatedPlan.name}".`);
      setPlans((current) =>
        current.map((plan) =>
          plan.plan_id === updatedPlan.plan_id ? updatedPlan : plan,
        ),
      );
      setPendingRoute(null);
      navigate("/travel-plans", { state: { planId: updatedPlan.plan_id } });
    } catch (reason) {
      setRouteActionMessage(messageFor(reason));
    } finally {
      setIsAddingRoute(false);
    }
  }

  function applySearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(0);
  }

  const totalPages = result ? Math.ceil(result.total / PAGE_SIZE) : 0;
  const canPrevious = page > 0;
  const canNext = result ? (page + 1) * PAGE_SIZE < result.total : false;

  return (
    <section className="explorer-page">
      <div className="page-heading explorer-heading">
        <div>
          <span className="eyebrow">Aviation Explorer</span>
          <h1>Explore the route network.</h1>
          <p>Search imported aviation records by airport, airline, or route.</p>
        </div>
      </div>
      <p className="data-notice">
        Aviation information is imported demonstration data, not live flight schedules.
      </p>
      <div className="explorer-tabs" role="tablist" aria-label="Aviation data">
        {(["airports", "airlines", "routes"] as Section[]).map((item) => (
          <button
            aria-selected={section === item}
            className={section === item ? "explorer-tab explorer-tab-active" : "explorer-tab"}
            key={item}
            onClick={() => setSection(item)}
            role="tab"
            type="button"
          >
            {item[0].toUpperCase() + item.slice(1)}
          </button>
        ))}
      </div>
      <form className="explorer-filters" onSubmit={applySearch}>
        {section !== "routes" && (
          <label className="search-field">
            Search
            <input
              onChange={(event) => setQuery(event.target.value)}
              placeholder={section === "airports" ? "Name, city, country, IATA" : "Name, country, IATA, ICAO"}
              value={query}
            />
          </label>
        )}
        {section === "airlines" && (
          <label>
            Departure airport ID
            <input inputMode="numeric" onChange={(event) => setAirportFilter(event.target.value)} placeholder="Optional" value={airportFilter} />
          </label>
        )}
        {section === "routes" && (
          <>
            <label>Airline ID<input inputMode="numeric" onChange={(event) => setAirlineFilter(event.target.value)} placeholder="Optional" value={airlineFilter} /></label>
            <label>Departure airport ID<input inputMode="numeric" onChange={(event) => setOriginFilter(event.target.value)} placeholder="Optional" value={originFilter} /></label>
            <label>Destination airport ID<input inputMode="numeric" onChange={(event) => setDestinationFilter(event.target.value)} placeholder="Optional" value={destinationFilter} /></label>
          </>
        )}
        <button className="button button-primary" type="submit">Search</button>
      </form>
      <div className="explorer-layout">
        <section className="panel explorer-results">
          <div className="panel-heading">
            <div><span className="eyebrow">{section}</span><h2>{result ? `${result.total} records` : "Records"}</h2></div>
          </div>
          {isLoading ? <p className="table-state">Loading records…</p> :
            error ? <p className="feedback feedback-error" role="alert">{error}</p> :
              !result || result.items.length === 0 ? <p className="table-state">No records match these filters.</p> :
                <ExplorerTable
                  section={section}
                  items={result.items}
                  onAddRoute={(item) => void beginAddRoute(item)}
                  onSelect={(item) => void showDetail(item)}
                />}
          {result && result.total > 0 && (
            <div className="pagination">
              <button className="button button-quiet" disabled={!canPrevious || isLoading} onClick={() => setPage((current) => current - 1)} type="button">Previous</button>
              <span>Page {page + 1} of {totalPages}</span>
              <button className="button button-quiet" disabled={!canNext || isLoading} onClick={() => setPage((current) => current + 1)} type="button">Next</button>
            </div>
          )}
        </section>
        <DetailPanel
          detail={detail}
          error={detailError}
          isAddingRoute={isAddingRoute}
          isLoading={isDetailLoading}
          isPlansLoading={isPlansLoading}
          onAddRoute={() => {
            if (selected && "route_id" in selected) void beginAddRoute(selected);
          }}
          onCancelAdd={() => {
            setPendingRoute(null);
            setRouteActionMessage("");
          }}
          onConfirmAdd={() => void addRouteToPlan()}
          pendingRoute={pendingRoute}
          plans={plans}
          routeActionMessage={routeActionMessage}
          selected={selected}
          targetPlanId={targetPlanId}
          onTargetPlanChange={setTargetPlanId}
        />
      </div>
    </section>
  );
}

function ExplorerTable({ section, items, onAddRoute, onSelect }: {
  section: Section;
  items: RecordItem[];
  onSelect: (item: RecordItem) => void;
  onAddRoute: (item: RouteSummary) => void;
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{section === "airports" ? <><th>ID</th><th>Name</th><th>City</th><th>Country</th><th>IATA</th></> :
          section === "airlines" ? <><th>ID</th><th>Name</th><th>Country</th><th>IATA</th><th>ICAO</th></> :
            <>            <th>ID</th><th>Airline</th><th>Departure</th><th>Arrival</th><th>Stops</th><th>Action</th></>}</tr></thead>
        <tbody>{items.map((item) => {
          const label = section === "airports" ? (item as Airport).name : section === "airlines" ? (item as Airline).name : `Route ${(item as RouteSummary).route_id}`;
          return <tr className="clickable-row" key={section === "airports" ? (item as Airport).airport_id : section === "airlines" ? (item as Airline).airline_id : (item as RouteSummary).route_id} onClick={() => onSelect(item)} tabIndex={0} onKeyDown={(event) => { if (event.key === "Enter") onSelect(item); }}>
            {section === "airports" ? <><td>{(item as Airport).airport_id}</td><td className="account-name">{label}</td><td>{value((item as Airport).city)}</td><td>{value((item as Airport).country)}</td><td>{value((item as Airport).iata_code)}</td></> :
              section === "airlines" ? <><td>{(item as Airline).airline_id}</td><td className="account-name">{label}</td><td>{value((item as Airline).country)}</td><td>{value((item as Airline).iata_code)}</td><td>{value((item as Airline).icao_code)}</td></> :
                <><td>{(item as RouteSummary).route_id}</td><td>{value((item as RouteSummary).airline_iata)} ({(item as RouteSummary).airline_id})</td><td>{value((item as RouteSummary).origin_iata)} ({(item as RouteSummary).origin_airport_id})</td><td>{value((item as RouteSummary).destination_iata)} ({(item as RouteSummary).destination_airport_id})</td><td>{(item as RouteSummary).stops}</td><td><button className="text-button" onClick={(event) => { event.stopPropagation(); onAddRoute(item as RouteSummary); }} type="button">Add to Plan</button></td></>}
          </tr>;
        })}</tbody>
      </table>
    </div>
  );
}

function DetailPanel({
  detail,
  error,
  isAddingRoute,
  isLoading,
  isPlansLoading,
  onAddRoute,
  onCancelAdd,
  onConfirmAdd,
  pendingRoute,
  plans,
  routeActionMessage,
  selected,
  targetPlanId,
  onTargetPlanChange,
}: {
  detail: Airport | Airline | RouteDetails | null;
  error: string;
  isAddingRoute: boolean;
  isLoading: boolean;
  isPlansLoading: boolean;
  onAddRoute: () => void;
  onCancelAdd: () => void;
  onConfirmAdd: () => void;
  pendingRoute: RouteSummary | null;
  plans: TravelPlan[];
  routeActionMessage: string;
  selected: RecordItem | null;
  targetPlanId: number | null;
  onTargetPlanChange: (planId: number) => void;
}) {
  return (
    <aside className="panel detail-panel">
      <span className="eyebrow">Details</span>
      {!selected ? <p className="table-state">Select a record to view details.</p> :
        isLoading ? <p className="table-state">Loading details…</p> :
          error ? <p className="feedback feedback-error" role="alert">{error}</p> :
            detail ? <DetailContent detail={detail} /> : null}
      {detail && "route_id" in detail && !pendingRoute && (
        <button className="button button-primary button-wide route-add-button" onClick={onAddRoute} type="button">
          Add to Plan
        </button>
      )}
      {pendingRoute && (
        <div className="route-picker">
          <span className="eyebrow">Add route to plan</span>
          <p className="route-picker-summary">
            Route {pendingRoute.route_id}: {value(pendingRoute.origin_iata)} → {value(pendingRoute.destination_iata)}
          </p>
          {isPlansLoading ? <p className="table-state">Loading your plans…</p> :
            plans.length === 0 ? <p className="feedback feedback-error">{routeActionMessage}</p> :
              <>
                <label>
                  Travel plan
                  <select
                    disabled={isAddingRoute}
                    onChange={(event) => onTargetPlanChange(Number(event.target.value))}
                    value={targetPlanId ?? ""}
                  >
                    {plans.map((plan) => (
                      <option key={plan.plan_id} value={plan.plan_id}>
                        {plan.name}{plan.routes.includes(pendingRoute.route_id) ? " (already added)" : ""}
                      </option>
                    ))}
                  </select>
                </label>
                {routeActionMessage && <p className="feedback feedback-error">{routeActionMessage}</p>}
                <div className="form-actions">
                  <button
                    className="button button-primary"
                    disabled={isAddingRoute || targetPlanId === null || plans.find((plan) => plan.plan_id === targetPlanId)?.routes.includes(pendingRoute.route_id) === true}
                    onClick={onConfirmAdd}
                    type="button"
                  >
                    {isAddingRoute ? "Adding…" : "Add route"}
                  </button>
                  <button className="button button-quiet" disabled={isAddingRoute} onClick={onCancelAdd} type="button">Cancel</button>
                </div>
              </>}
        </div>
      )}
    </aside>
  );
}

function DetailContent({ detail }: { detail: Airport | Airline | RouteDetails }) {
  if ("route_id" in detail) {
    return <><h2>Route {detail.route_id}</h2><dl className="detail-list">
      <dt>Airline</dt><dd>{detail.airline?.name ?? value(detail.airline_iata)} ({detail.airline_id})</dd>
      <dt>Departure</dt><dd>{detail.origin_airport?.name ?? value(detail.origin_iata)} ({detail.origin_airport_id})</dd>
      <dt>Arrival</dt><dd>{detail.destination_airport?.name ?? value(detail.destination_iata)} ({detail.destination_airport_id})</dd>
      <dt>Stops</dt><dd>{detail.stops}</dd><dt>Codeshare</dt><dd>{value(detail.codeshare)}</dd><dt>Equipment</dt><dd>{value(detail.equipment)}</dd>
    </dl></>;
  }
  if ("airport_id" in detail) {
    return <><h2>{detail.name}</h2><dl className="detail-list"><dt>ID</dt><dd>{detail.airport_id}</dd><dt>City</dt><dd>{value(detail.city)}</dd><dt>Country</dt><dd>{value(detail.country)}</dd><dt>IATA / ICAO</dt><dd>{value(detail.iata_code)} / {value(detail.icao_code)}</dd><dt>Coordinates</dt><dd>{value(detail.latitude)}, {value(detail.longitude)}</dd><dt>Altitude</dt><dd>{value(detail.altitude)}</dd><dt>Timezone</dt><dd>{value(detail.timezone)}</dd></dl></>;
  }
  return <><h2>{detail.name}</h2><dl className="detail-list"><dt>ID</dt><dd>{detail.airline_id}</dd><dt>Country</dt><dd>{value(detail.country)}</dd><dt>IATA / ICAO</dt><dd>{value(detail.iata_code)} / {value(detail.icao_code)}</dd></dl></>;
}
