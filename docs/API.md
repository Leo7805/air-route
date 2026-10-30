# AirRoute — API Reference

A concise endpoint index for **AirRoute — Airline Route Explorer & Travel
Planner**. Swagger/OpenAPI at `http://127.0.0.1:5000/` is the detailed source
of truth for schemas, parameters and response codes.

**Base URL (local):** `http://127.0.0.1:5000`

## Access conventions

- **Public:** No authentication required.
- **Authenticated:** A valid JWT for an active User or Admin.
- **Admin:** An active Admin account only.
- **Owner:** The authenticated account owns the travel plan, including Admin
  accounts accessing their own plans.

Protected requests use an `Authorization: Bearer <JWT>` header.

## Authentication

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| POST | `/auth/login` | Sign in and receive a JWT | Public |
| GET | `/auth/me` | Get the current account | Authenticated |

## Accounts

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/accounts` | List all accounts | Admin |
| POST | `/accounts` | Create a User account | Admin |
| PATCH | `/accounts/{account_id}` | Activate or deactivate a User account | Admin |
| DELETE | `/accounts/{account_id}` | Delete a User account | Admin |

## Data import

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| POST | `/imports` | Import one or more airport, airline or route CSV datasets | Admin |

## Airports

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/airports` | Search and list airports | Authenticated |
| GET | `/airports/{airport_id}` | Get airport details | Authenticated |

## Airlines

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/airlines` | Search and list airlines | Authenticated |
| GET | `/airlines/{airline_id}` | Get airline details | Authenticated |

## Routes

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/routes` | Filter and list routes | Authenticated |
| GET | `/routes/{route_id}` | Get route and related aviation details | Authenticated |

## Travel plans

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/travel-plans` | List the current account's plans | Authenticated |
| POST | `/travel-plans` | Create a travel plan | Authenticated |
| GET | `/travel-plans/{plan_id}` | Get an owned travel plan | Owner |
| PUT | `/travel-plans/{plan_id}` | Update an owned travel plan | Owner |
| DELETE | `/travel-plans/{plan_id}` | Delete an owned travel plan | Owner |
| POST | `/travel-plans/{plan_id}/routes` | Add a route to an owned plan | Owner |
| DELETE | `/travel-plans/{plan_id}/routes/{route_id}` | Remove a route from an owned plan | Owner |
| GET | `/travel-plans/export` | Export the current account's plans as JSON or PNG | Authenticated |
