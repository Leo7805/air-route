export type AccountRole = "Admin" | "User";

export interface Account {
  id: number;
  username: string;
  role: AccountRole;
  is_active: boolean;
}

export interface LoginResponse {
  access_token: string;
}

export interface ApiErrorPayload {
  message?: string;
}

export interface Page<T> {
  total: number;
  limit: number;
  offset: number;
  items: T[];
}

export interface ResourceLinks {
  self: string;
  [key: string]: string;
}

export interface Airport {
  airport_id: number;
  name: string;
  city: string | null;
  country: string | null;
  iata_code: string | null;
  icao_code: string | null;
  latitude: number | null;
  longitude: number | null;
  altitude: number | null;
  timezone: string | null;
  links: ResourceLinks;
}

export interface Airline {
  airline_id: number;
  name: string;
  iata_code: string | null;
  icao_code: string | null;
  country: string | null;
  links: ResourceLinks;
}

export interface RouteSummary {
  route_id: number;
  airline_id: number;
  airline_iata: string | null;
  origin_airport_id: number;
  origin_iata: string | null;
  destination_airport_id: number;
  destination_iata: string | null;
  codeshare: string | null;
  stops: number;
  equipment: string | null;
  links: ResourceLinks;
}

export interface RouteDetails extends RouteSummary {
  airline: Airline | null;
  origin_airport: Airport | null;
  destination_airport: Airport | null;
}
