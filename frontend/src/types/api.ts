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
