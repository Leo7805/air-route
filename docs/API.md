# AirRoute — API Reference

A concise endpoint index for **AirRoute — Airline Route Explorer & Travel Planner**. For detailed request/response schemas, parameters, and status codes, use the automatically generated Swagger documentation.

**Base URL (local):** `http://127.0.0.1:5000`  
**Interactive API documentation:** [Swagger UI](http://127.0.0.1:5000/) · [OpenAPI Specification](http://127.0.0.1:5000/swagger.json)

## Access Conventions

- **Public:** No authentication required.
- **Authenticated:** Valid JWT belonging to an active User or Admin.
- **Admin:** Active Admin account only.
- **Owner:** The authenticated account must own the travel plan, including when signed in as Admin.

Protected requests use `Authorization: Bearer <access_token>`.

## 1. Authentication

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| POST | `/auth/login` | Sign in and receive a JWT | Public |
| GET | `/auth/me` | Get the current account | Authenticated |

## 2. Accounts

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/accounts` | List all accounts | Admin |
| POST | `/accounts` | Create a User account | Admin |
| PATCH | `/accounts/{account_id}` | Activate or deactivate a User account | Admin |
| DELETE | `/accounts/{account_id}` | Delete a User account | Admin |

## 3. Data Import

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| POST | `/imports` | Import airports, airlines, and/or routes from CSV | Admin |

## 4. Airports

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/airports` | Search and list airports | Authenticated |
| GET | `/airports/{airport_id}` | Get airport details | Authenticated |

## 5. Airlines

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/airlines` | Search and list airlines | Authenticated |
| GET | `/airlines/{airline_id}` | Get airline details | Authenticated |

## 6. Routes

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/routes` | Filter and list routes | Authenticated |
| GET | `/routes/{route_id}` | Get route and related aviation details | Authenticated |

## 7. Travel Plans

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/travel-plans` | List my travel plans | Authenticated |
| POST | `/travel-plans` | Create a travel plan | Authenticated |
| GET | `/travel-plans/{plan_id}` | Get my travel plan | Owner |
| PUT | `/travel-plans/{plan_id}` | Update my travel plan | Owner |
| DELETE | `/travel-plans/{plan_id}` | Delete my travel plan | Owner |
| POST | `/travel-plans/{plan_id}/routes` | Add a route to my plan | Owner |
| DELETE | `/travel-plans/{plan_id}/routes/{route_id}` | Remove a route from my plan | Owner |
| GET | `/travel-plans/export` | Export my plans as JSON or PNG | Authenticated |

## Key Notes

- Travel plans are private: Admin accounts cannot access other accounts' travel plans.
- CSV imports reject changes that would remove or modify routes referenced by travel plans.
- Exports support `?format=json` (download) and `?format=image` (PNG visualisation).
- Aviation data comes from imported CSV datasets, not live flight schedules or ticket pricing.
- The local URL above assumes the Flask server is running on port `5000`; change it if your configuration differs.

**Coverage:** 21 HTTP operations across 16 paths.
