type IconName = "globe" | "calendar" | "user" | "shield" | "logout" | "upload" | "users" | "close" | "info";

const paths: Record<IconName, React.ReactNode> = {
  globe: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a17 17 0 0 1 0 18 17 17 0 0 1 0-18Z" /></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M7 3v4m10-4v4M3 11h18" /></>,
  user: <><circle cx="12" cy="7" r="4" /><path d="M4 21v-2a8 8 0 0 1 16 0v2" /></>,
  shield: <><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z" /><path d="m8 12 3 3 5-6" /></>,
  logout: <><path d="M9 4H4v16h5m6-12 4 4-4 4m-7-4h11" /></>,
  upload: <><path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6" /></>,
  users: <><circle cx="9" cy="7" r="4" /><path d="M2 21v-2a7 7 0 0 1 14 0v2m0-18a4 4 0 0 1 0 8m3 4a7 7 0 0 1 3 6" /></>,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6m0-10v.01" /></>,
};

export function Icon({ name }: { name: IconName }) {
  return <svg aria-hidden="true" className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}
