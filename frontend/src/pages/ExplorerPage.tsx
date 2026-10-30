import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { ExplorerDetails } from "../components/ExplorerDetails";
import { AddRouteDialog } from "../components/AddRouteDialog";
import { Icon } from "../components/Icon";
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
  const detailTrigger = useRef<HTMLElement | null>(null);

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
    detailTrigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
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
        <h1>Aviation Explorer</h1>
        <p className="data-notice"><Icon name="info" />Imported demo data · Not live schedules</p>
      </div>
      <div className="explorer-tabs" role="tablist" aria-label="Aviation data">
        {(["airports", "airlines", "routes"] as Section[]).map((item) => (
          <button
            aria-selected={section === item}
            aria-controls="explorer-panel"
            id={`explorer-tab-${item}`}
            tabIndex={section === item ? 0 : -1}
            onKeyDown={(event) => {
              const tabs: Section[] = ["airports", "airlines", "routes"];
              const index = tabs.indexOf(item);
              const next = event.key === "ArrowRight" ? tabs[(index + 1) % 3] : event.key === "ArrowLeft" ? tabs[(index + 2) % 3] : event.key === "Home" ? tabs[0] : event.key === "End" ? tabs[2] : null;
              if (next) { event.preventDefault(); setSection(next); document.getElementById(`explorer-tab-${next}`)?.focus(); }
            }}
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
        <button className="button button-quiet" onClick={() => { setQuery(""); setAirportFilter(""); setAirlineFilter(""); setOriginFilter(""); setDestinationFilter(""); setPage(0); }} type="button">Clear</button>
      </form>
      <div aria-labelledby={`explorer-tab-${section}`} className="explorer-layout" id="explorer-panel" role="tabpanel">
        <section className="panel explorer-results">
          <div className="panel-heading">
            <div><h2 className="section-title">{section}</h2><span className="count-label">{result ? `${result.total} imported records` : "Imported records"}</span></div><span className="count-label">Select a row for details</span>
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
              <span className="page-number">{page + 1} / {totalPages}</span>
              <button className="button button-quiet" disabled={!canNext || isLoading} onClick={() => setPage((current) => current + 1)} type="button">Next</button>
            </div>
          )}
        </section>
        {selected && <ExplorerDetails
          detail={detail} error={detailError} isLoading={isDetailLoading}
          title={section === "routes" ? "Route details" : section === "airports" ? "Airport details" : "Airline details"}
          trigger={detailTrigger.current} modalOpen={pendingRoute !== null}
          onClose={() => { ++detailRequestId.current; setSelected(null); setDetail(null); }}
          onAddRoute={"route_id" in selected ? () => void beginAddRoute(selected) : undefined}
        />}
        {pendingRoute && <AddRouteDialog route={pendingRoute} plans={plans} isLoading={isPlansLoading}
          isAdding={isAddingRoute} message={routeActionMessage} targetPlanId={targetPlanId}
          onTargetPlanChange={setTargetPlanId} onConfirm={() => void addRouteToPlan()}
          onClose={() => { setPendingRoute(null); setRouteActionMessage(""); }} />}
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
          return <tr className="clickable-row" key={section === "airports" ? (item as Airport).airport_id : section === "airlines" ? (item as Airline).airline_id : (item as RouteSummary).route_id} onClick={() => onSelect(item)} tabIndex={0} onKeyDown={(event) => { if (event.target === event.currentTarget && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); onSelect(item); } }}>
            {section === "airports" ? <><td>{(item as Airport).airport_id}</td><td className="account-name">{label}</td><td>{value((item as Airport).city)}</td><td>{value((item as Airport).country)}</td><td>{value((item as Airport).iata_code)}</td></> :
              section === "airlines" ? <><td>{(item as Airline).airline_id}</td><td className="account-name">{label}</td><td>{value((item as Airline).country)}</td><td>{value((item as Airline).iata_code)}</td><td>{value((item as Airline).icao_code)}</td></> :
                <><td>{(item as RouteSummary).route_id}</td><td>{value((item as RouteSummary).airline_iata)} ({(item as RouteSummary).airline_id})</td><td>{value((item as RouteSummary).origin_iata)} ({(item as RouteSummary).origin_airport_id})</td><td>{value((item as RouteSummary).destination_iata)} ({(item as RouteSummary).destination_airport_id})</td><td>{(item as RouteSummary).stops}</td><td><button className="button button-tint" onClick={(event) => { event.stopPropagation(); onAddRoute(item as RouteSummary); }} type="button">+ Add to Plan</button></td></>}
          </tr>;
        })}</tbody>
      </table>
    </div>
  );
}
