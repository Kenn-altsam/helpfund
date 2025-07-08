export interface User {
  id: string;
  email: string;
  full_name: string;
  is_verified: boolean;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Company {
  id: string;
  bin: string;
  name: string;
  oked: string;
  activity: string;
  kato: string;
  locality: string;
  krp: string;
  size: string;
  annual_tax_paid?: number;
  tax_2020?: number;
  tax_2021?: number;
  tax_2022?: number;
  tax_2023?: number;
  tax_2024?: number;
  tax_2025?: number;
  last_tax_update?: string;
  contacts?: string;
  region?: string;
  industry?: string;
  taxes?: string;
  website?: string;
}

export interface ChatHistoryItem {
  id: string;
  userPrompt: string;
  aiResponse: Company[];
  created_at: string;
  threadId: string | null;
  assistantId: string | null;
}

export interface GlobalState {
  history: ChatHistoryItem[];
  considerationList: Company[];
  user: User | null;
  isLoading: boolean;
}

export type GlobalAction =
  | { type: 'ADD_HISTORY'; payload: ChatHistoryItem }
  | { type: 'LOAD_HISTORY'; payload: ChatHistoryItem[] }
  | { type: 'DELETE_HISTORY'; payload: string }
  | { type: 'UPDATE_HISTORY'; payload: ChatHistoryItem }
  | { type: 'ADD_CONSIDERATION'; payload: Company }
  | { type: 'REMOVE_CONSIDERATION'; payload: string }
  | { type: 'SET_USER'; payload: User | null }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'CLEAR_STATE' }
  | { type: 'CLEAR_STATE_PRESERVE_LIST' }
  | { type: 'SET_CONSIDERATION_LIST'; payload: Company[] };

export interface ApiResponse<T> {
  data: T;
  message?: string;
  success: boolean;
}

export interface ChatRequest {
  user_input: string;
  history: Array<{ role: 'user' | 'assistant'; content: string }>;
  location?: string;
  assistant_id?: string;
  thread_id?: string;
}

export interface ChatResponse {
  message: string;
  companies?: Company[];
  assistant_id?: string;
  thread_id?: string;
}

export interface AuthCredentials {
  email: string;
  password: string;
  full_name?: string;
}