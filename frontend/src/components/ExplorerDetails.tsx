import { useEffect, useLayoutEffect, useRef } from "react";
import type { Airport, Airline, RouteDetails } from "../types/api";
import { Icon } from "./Icon";

function value(value: string | number | null | undefined) {
  return value === null || value === undefined || value === "" ? "—" : value;
}

/** Shows record details without blocking the table or locking document scrolling. */
export function ExplorerDetails({ detail, error, isLoading, title, trigger, modalOpen, onClose, onAddRoute }: {
  detail: Airport | Airline | RouteDetails | null;
  error: string;
  isLoading: boolean;
  title: string;
  trigger: HTMLElement | null;
  modalOpen: boolean;
  onClose: () => void;
  onAddRoute?: () => void;
}) {
  const panel = useRef<HTMLElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const returnFocus = useRef(trigger);

  useEffect(() => { close.current?.focus({ preventScroll: true }); }, []);
  useEffect(() => { returnFocus.current = trigger; }, [trigger]);
  // Restore focus before React removes the drawer from the document.
  useLayoutEffect(() => {
    const element = panel.current;
    return () => {
      if (element?.contains(document.activeElement)) returnFocus.current?.focus({ preventScroll: true });
    };
  }, []);
  useEffect(() => {
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape" && !modalOpen) { event.preventDefault(); onClose(); }
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [modalOpen, onClose]);

  return <aside aria-labelledby="detail-title" className="detail-drawer" ref={panel}>
    <header className="drawer-heading"><h2 id="detail-title">{title}</h2><button aria-label="Close details" className="button button-quiet icon-button" onClick={onClose} ref={close} type="button"><Icon name="close" /></button></header>
    <div className="drawer-body" aria-busy={isLoading}>
      {isLoading ? <p className="table-state" role="status">Loading details…</p> : error ? <p className="feedback feedback-error" role="alert">{error}</p> : detail ? <DetailContent detail={detail} /> : null}
    </div>
    <footer className="drawer-footer"><button className="button button-quiet" onClick={onClose} type="button">Close</button>{onAddRoute && <button className="button button-primary" onClick={onAddRoute} type="button">+ Add to Plan</button>}</footer>
  </aside>;
}

function DetailContent({ detail }: { detail: Airport | Airline | RouteDetails }) {
  if ("route_id" in detail) {
    return <><span className="eyebrow">Route #{detail.route_id}</span><h2>{value(detail.origin_iata)} → {value(detail.destination_iata)}</h2><p className="muted">{detail.airline?.name ?? value(detail.airline_iata)}</p>
      <dl className="route-detail-list">
        <div><dt>Departure</dt><dd>{value(detail.origin_iata)}<small>{detail.origin_airport?.name ?? "Airport"} · ID {detail.origin_airport_id}</small></dd></div>
        <div><dt>Arrival</dt><dd>{value(detail.destination_iata)}<small>{detail.destination_airport?.name ?? "Airport"} · ID {detail.destination_airport_id}</small></dd></div>
        <div><dt>Airline</dt><dd>{value(detail.airline_iata)}<small>{detail.airline?.name ?? "Airline"} · ID {detail.airline_id}</small></dd></div>
        <div><dt>Stops</dt><dd>{detail.stops}</dd></div>
      </dl>
      <dl className="detail-list route-extra-details"><dt>Codeshare</dt><dd>{value(detail.codeshare)}</dd><dt>Equipment</dt><dd>{value(detail.equipment)}</dd></dl>
    </>;
  }
  if ("airport_id" in detail) {
    return <><h2>{detail.name}</h2><dl className="detail-list"><dt>ID</dt><dd>{detail.airport_id}</dd><dt>City</dt><dd>{value(detail.city)}</dd><dt>Country</dt><dd>{value(detail.country)}</dd><dt>IATA / ICAO</dt><dd>{value(detail.iata_code)} / {value(detail.icao_code)}</dd><dt>Coordinates</dt><dd>{value(detail.latitude)}, {value(detail.longitude)}</dd><dt>Altitude</dt><dd>{value(detail.altitude)}</dd><dt>Timezone</dt><dd>{value(detail.timezone)}</dd></dl></>;
  }
  return <><h2>{detail.name}</h2><dl className="detail-list"><dt>ID</dt><dd>{detail.airline_id}</dd><dt>Country</dt><dd>{value(detail.country)}</dd><dt>IATA / ICAO</dt><dd>{value(detail.iata_code)} / {value(detail.icao_code)}</dd></dl></>;
}
