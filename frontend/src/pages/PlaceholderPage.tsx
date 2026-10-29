import { useLocation } from "react-router-dom";

const pageCopy: Record<string, { eyebrow: string; title: string; body: string }> = {
  "/explorer": {
    eyebrow: "Aviation Explorer",
    title: "Your route network starts here.",
    body: "Airport, airline, and route search will be connected in the next frontend phase.",
  },
  "/travel-plans": {
    eyebrow: "Travel Plans",
    title: "Keep your routes together.",
    body: "Travel plan management will be connected to the existing API in the next frontend phase.",
  },
  "/imports": {
    eyebrow: "Data Import",
    title: "Keep aviation data current.",
    body: "CSV import controls for administrators are planned for the next frontend phase.",
  },
  "/accounts": {
    eyebrow: "Account Management",
    title: "Manage account access.",
    body: "Administrator account controls are planned for the next frontend phase.",
  },
};

export function PlaceholderPage() {
  const { pathname } = useLocation();
  const copy = pageCopy[pathname] ?? pageCopy["/explorer"];

  return (
    <section className="empty-page">
      <span className="eyebrow">{copy.eyebrow}</span>
      <h1>{copy.title}</h1>
      <p>{copy.body}</p>
      <span className="status-pill">Foundation ready</span>
    </section>
  );
}
