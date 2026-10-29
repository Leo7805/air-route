import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import { useAuth } from "../auth/AuthContext";
import { ApiError, api } from "../lib/api";
import type {
  Airline,
  Airport,
  Page,
  RouteDetails,
  RouteSummary,
} from "../types/api";

type Section = "airports" | "airlines" | "routes";
type RecordItem = Airport | Airline | RouteSummary;

const PAGE_SIZE = 12;

function messageFor(reason: unknown) {
  return reason instanceof ApiError ? reason.message : "Unable to load aviation data.";
}

function value(value: string | number | null | undefined) {
  return value === null || value === undefined || value === "" ? "—" : value;
}

export function ExplorerPage() {
  const { token } = useAuth();
  const [section, setSection] = useState<Section>("airports");
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
                <ExplorerTable section={section} items={result.items} onSelect={(item) => void showDetail(item)} />}
          {result && result.total > 0 && (
            <div className="pagination">
              <button className="button button-quiet" disabled={!canPrevious || isLoading} onClick={() => setPage((current) => current - 1)} type="button">Previous</button>
              <span>Page {page + 1} of {totalPages}</span>
              <button className="button button-quiet" disabled={!canNext || isLoading} onClick={() => setPage((current) => current + 1)} type="button">Next</button>
            </div>
          )}
        </section>
        <DetailPanel detail={detail} error={detailError} isLoading={isDetailLoading} selected={selected} />
      </div>
    </section>
  );
}

function ExplorerTable({ section, items, onSelect }: {
  section: Section;
  items: RecordItem[];
  onSelect: (item: RecordItem) => void;
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{section === "airports" ? <><th>ID</th><th>Name</th><th>City</th><th>Country</th><th>IATA</th></> :
          section === "airlines" ? <><th>ID</th><th>Name</th><th>Country</th><th>IATA</th><th>ICAO</th></> :
            <><th>ID</th><th>Airline</th><th>Departure</th><th>Arrival</th><th>Stops</th></>}</tr></thead>
        <tbody>{items.map((item) => {
          const label = section === "airports" ? (item as Airport).name : section === "airlines" ? (item as Airline).name : `Route ${(item as RouteSummary).route_id}`;
          return <tr className="clickable-row" key={section === "airports" ? (item as Airport).airport_id : section === "airlines" ? (item as Airline).airline_id : (item as RouteSummary).route_id} onClick={() => onSelect(item)} tabIndex={0} onKeyDown={(event) => { if (event.key === "Enter") onSelect(item); }}>
            {section === "airports" ? <><td>{(item as Airport).airport_id}</td><td className="account-name">{label}</td><td>{value((item as Airport).city)}</td><td>{value((item as Airport).country)}</td><td>{value((item as Airport).iata_code)}</td></> :
              section === "airlines" ? <><td>{(item as Airline).airline_id}</td><td className="account-name">{label}</td><td>{value((item as Airline).country)}</td><td>{value((item as Airline).iata_code)}</td><td>{value((item as Airline).icao_code)}</td></> :
                <><td>{(item as RouteSummary).route_id}</td><td>{value((item as RouteSummary).airline_iata)} ({(item as RouteSummary).airline_id})</td><td>{value((item as RouteSummary).origin_iata)} ({(item as RouteSummary).origin_airport_id})</td><td>{value((item as RouteSummary).destination_iata)} ({(item as RouteSummary).destination_airport_id})</td><td>{(item as RouteSummary).stops}</td></>}
          </tr>;
        })}</tbody>
      </table>
    </div>
  );
}

function DetailPanel({ detail, error, isLoading, selected }: {
  detail: Airport | Airline | RouteDetails | null;
  error: string;
  isLoading: boolean;
  selected: RecordItem | null;
}) {
  return (
    <aside className="panel detail-panel">
      <span className="eyebrow">Details</span>
      {!selected ? <p className="table-state">Select a record to view details.</p> :
        isLoading ? <p className="table-state">Loading details…</p> :
          error ? <p className="feedback feedback-error" role="alert">{error}</p> :
            detail ? <DetailContent detail={detail} /> : null}
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
