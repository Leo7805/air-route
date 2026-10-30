import type {
  Account,
  ApiErrorPayload,
  Airline,
  Airport,
  LoginResponse,
  Page,
  RouteDetails,
  RouteSummary,
  TravelPlan,
  TravelPlanList,
  ImportResponse,
} from "../types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function responseError(response: Response) {
  const contentType = response.headers.get("Content-Type") ?? "";
  let message: string | undefined;
  if (contentType.includes("application/json")) {
    const body = await response.text();
    if (body) {
      try {
        const payload = JSON.parse(body) as ApiErrorPayload;
        message = payload.message;
      } catch {
        message = undefined;
      }
    }
  }
  throw new ApiError(
    message ?? `Request failed with status ${response.status}`,
    response.status,
  );
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });
  const contentType = response.headers.get("Content-Type") ?? "";
  let payload: ApiErrorPayload | T | undefined;
  if (response.status !== 204 && contentType.includes("application/json")) {
    if (typeof response.text === "function") {
      const responseBody = await response.text();
      if (responseBody) {
        payload = JSON.parse(responseBody) as ApiErrorPayload | T;
      }
    } else {
      payload = (await response.json()) as ApiErrorPayload | T;
    }
  }

  if (!response.ok) {
    const message =
      typeof payload === "object" &&
      payload !== null &&
      "message" in payload &&
      typeof payload.message === "string"
        ? payload.message
        : `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status);
  }

  return payload as T;
}

export const api = {
  login(username: string, password: string) {
    return request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
  },

  me(token: string, signal?: AbortSignal) {
    return request<Account>("/auth/me", { signal }, token);
  },

  airports(token: string, params: { q?: string; limit: number; offset: number }, signal?: AbortSignal) {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    query.set("limit", String(params.limit));
    query.set("offset", String(params.offset));
    return request<Page<Airport>>(`/airports?${query}`, { signal }, token);
  },

  airport(token: string, airportId: number, signal?: AbortSignal) {
    return request<Airport>(`/airports/${airportId}`, { signal }, token);
  },

  airlines(
    token: string,
    params: { q?: string; airportId?: number; limit: number; offset: number },
    signal?: AbortSignal,
  ) {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.airportId !== undefined) {
      query.set("airport_id", String(params.airportId));
    }
    query.set("limit", String(params.limit));
    query.set("offset", String(params.offset));
    return request<Page<Airline>>(`/airlines?${query}`, { signal }, token);
  },

  airline(token: string, airlineId: number, signal?: AbortSignal) {
    return request<Airline>(`/airlines/${airlineId}`, { signal }, token);
  },

  routes(
    token: string,
    params: {
      airlineId?: number;
      originAirportId?: number;
      destinationAirportId?: number;
      limit: number;
      offset: number;
    },
    signal?: AbortSignal,
  ) {
    const query = new URLSearchParams();
    if (params.airlineId !== undefined) {
      query.set("airline_id", String(params.airlineId));
    }
    if (params.originAirportId !== undefined) {
      query.set("origin_airport_id", String(params.originAirportId));
    }
    if (params.destinationAirportId !== undefined) {
      query.set("destination_airport_id", String(params.destinationAirportId));
    }
    query.set("limit", String(params.limit));
    query.set("offset", String(params.offset));
    return request<Page<RouteSummary>>(`/routes?${query}`, { signal }, token);
  },

  route(token: string, routeId: number, signal?: AbortSignal) {
    return request<RouteDetails>(`/routes/${routeId}`, { signal }, token);
  },

  travelPlans(token: string, signal?: AbortSignal) {
    return request<TravelPlanList>("/travel-plans", { signal }, token);
  },

  travelPlan(token: string, planId: number, signal?: AbortSignal) {
    return request<TravelPlan>(`/travel-plans/${planId}`, { signal }, token);
  },

  createTravelPlan(
    token: string,
    data: Pick<TravelPlan, "name" | "departure_date" | "return_date">,
  ) {
    return request<TravelPlan>("/travel-plans", {
      method: "POST",
      body: JSON.stringify(data),
    }, token);
  },

  updateTravelPlan(
    token: string,
    planId: number,
    data: Pick<TravelPlan, "name" | "departure_date" | "return_date">,
  ) {
    return request<TravelPlan>(`/travel-plans/${planId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }, token);
  },

  async deleteTravelPlan(token: string, planId: number): Promise<void> {
    await request<void>(`/travel-plans/${planId}`, {
      method: "DELETE",
    }, token);
  },

  addRouteToTravelPlan(token: string, planId: number, routeId: number) {
    return request<TravelPlan>(`/travel-plans/${planId}/routes`, {
      method: "POST",
      body: JSON.stringify({ route_id: routeId }),
    }, token);
  },

  async removeRouteFromTravelPlan(
    token: string,
    planId: number,
    routeId: number,
  ): Promise<void> {
    await request<void>(`/travel-plans/${planId}/routes/${routeId}`, {
      method: "DELETE",
    }, token);
  },

  async exportTravelPlans(
    token: string,
    format: "json" | "image",
  ): Promise<{ blob: Blob; filename: string }> {
    const response = await fetch(
      `${API_BASE_URL}/travel-plans/export?format=${format}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    if (!response.ok) {
      await responseError(response);
    }
    const contentDisposition = response.headers.get("Content-Disposition") ?? "";
    const filename =
      contentDisposition.match(/filename="?([^";]+)"?/i)?.[1] ??
      (format === "json" ? "travel-plans.json" : "upcoming-travel-plans.png");
    return { blob: await response.blob(), filename };
  },

  importDatasets(
    token: string,
    files: Partial<Record<"airports" | "airlines" | "routes", File>>,
  ) {
    const formData = new FormData();
    for (const dataset of ["airports", "airlines", "routes"] as const) {
      const file = files[dataset];
      if (file) formData.append(dataset, file);
    }
    return request<ImportResponse>("/imports", {
      method: "POST",
      body: formData,
    }, token);
  },

  accounts(token: string) {
    return request<Account[]>("/accounts", {}, token);
  },

  createAccount(token: string, username: string, password: string) {
    return request<Account>("/accounts", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }, token);
  },

  updateAccountStatus(token: string, accountId: number, isActive: boolean) {
    return request<Account>(`/accounts/${accountId}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: isActive }),
    }, token);
  },

  async deleteAccount(token: string, accountId: number): Promise<void> {
    await request<void>(`/accounts/${accountId}`, {
      method: "DELETE",
    }, token);
  },
};
