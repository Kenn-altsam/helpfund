export interface PaginationMetadata {
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface PaginatedResponse<T> {
  data: T;
  pagination?: PaginationMetadata;
}

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
  name?: string;
  oked: string;
  activity: string;
  kato: string;
  locality: string;
  krp: string;
  size: string;
  tax_data_2023?: number;
  tax_data_2024?: number;
  tax_data_2025?: number;
  contacts?: string; // Reverted to string as per current database schema
  website?: string;
}

export interface ChatHistoryItem {
  id: string;
  userPrompt: string;
  aiResponse: Company[];
  created_at: string;
  threadId: string;
  assistantId: string;
}

// === CHARITY RESEARCH TYPES ===
export interface GoogleSearchResult {
  title: string;
  link: string;
  snippet: string;
}

export interface CompanyCharityRequest {
  company_name: string;
  additional_context?: string;
}

export interface CompanyCharityResponse {
  status: 'success' | 'error';
  company_name: string;
  charity_info: GoogleSearchResult[];
  summary: string;
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
  metadata?: {
    pagination?: PaginationMetadata;
  };
}

export interface ChatRequest {
  user_input: string;
  chat_id?: string; // Используем chat_id для персистентности
  assistant_id?: string; // Оставляем для совместимости
  thread_id?: string; // Оставляем для совместимости
  page?: number;
}

export interface ChatResponse {
  message: string;
  companies?: Company[];
  chat_id?: string; // Основной ID для персистентности
  assistant_id?: string; // Для совместимости
  thread_id?: string; // Для совместимости
  pagination?: PaginationMetadata;
  updated_history?: Array<{ role: 'user' | 'assistant'; content: string; [key: string]: any }>;
}

export interface AuthCredentials {
  email: string;
  password: string;
  full_name?: string;
}