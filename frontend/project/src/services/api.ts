/// <reference types="vite/client" />

import axios, { AxiosResponse, AxiosError, InternalAxiosRequestConfig } from 'axios';
// Make sure ChatHistoryItem in '@/types' is flexible enough or add a new type for the sidebar list
// For example, if ChatHistoryItem is currently only for full chat history, you might need:
// interface ChatSidebarItem {
//   id: string; // or uuid.UUID if you have a specific UUID type
//   title: string;
//   updated_at: Date;
//   openaiThreadId?: string | null;
//   openaiAssistantId?: string | null;
// }
// For now, I'll assume ChatHistoryItem can correctly represent this simplified structure.
import { Company, ChatHistoryItem, User, ChatRequest, ChatResponse, AuthCredentials, AuthResponse } from '@/types';

declare global {
  interface ImportMetaEnv {
    readonly VITE_API_BASE_URL: string;
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

// Create axios instance with proper type annotations
const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true, // For http-only cookies
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for auth token with proper types
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling with proper types
api.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError<{ detail?: string }>) => {
    if (error.response?.status === 401) {
      // Only clear token and redirect for actual auth errors
      const authError = error.response?.data?.detail === "Could not validate credentials";
      if (authError) {
        localStorage.removeItem('access_token');
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

// Helper function to transform backend company data to frontend format
const transformCompanyData = (company: any): Company => {

  return {
    ...company,
    // Prefer existing fields if already present; otherwise map from backend-specific names
    name: company.name || 'Unnamed Company', // FIX: Ensure name is always a string
    region: company.region || company.locality,
    industry: company.industry || company.activity,
    contacts: company.contacts || null,
    website: company.website || null
  };
};

// Extend ChatResponse to include raw, unprocessed company data for advanced use cases
interface RawChatResponse extends ChatResponse {
  /**
   * Original companies array returned by the backend before any client-side transformation.
   * Can be useful for debugging or exporting untouched data.
   */
  rawCompanies?: any[];
}

// Helper function to generate a temporary unique ID for React keys when real ID is missing
const generateId = () => `temp-id-${Math.random().toString(36).substr(2, 9)}`;

// Companies API
export const companiesApi = {
  search: async (params: { location?: string; company_name?: string; limit?: number }) => {
    try {
      const response = await api.get('/companies/search', { params });
      return response.data.data.map(transformCompanyData);
    } catch (error) {
      console.error('Failed to search companies:', error);
      throw error;
    }
  },

  getByLocation: async (location: string, limit: number = 50) => {
    try {
      const response = await api.get(`/companies/by-location/${encodeURIComponent(location)}`, {
        params: { limit }
      });
      return response.data.data.map(transformCompanyData);
    } catch (error) {
      console.error('Failed to get companies by location:', error);
      throw error;
    }
  },

  getDetails: async (companyId: string) => {
    try {
      const response = await api.get(`/companies/${companyId}`);
      return transformCompanyData(response.data.data);
    } catch (error) {
      console.error('Failed to get company details:', error);
      throw error;
    }
  },

  getLocations: async () => {
    try {
      const response = await api.get('/companies/locations/list');
      return response.data.data;
    } catch (error) {
      console.error('Failed to get locations:', error);
      throw error;
    }
  },

  getTaxData: async (binNumber: string) => {
    try {
      const response = await api.get(`/companies/tax/${binNumber}`);
      return response.data.data;
    } catch (error) {
      console.error('Failed to get tax data:', error);
      throw error;
    }
  },

  translateCity: async (cityName: string) => {
    try {
      const response = await api.post('/companies/translations/translate-city', null, {
        params: { city_name: cityName }
      });
      return response.data.data;
    } catch (error) {
      console.error('Failed to translate city name:', error);
      throw error;
    }
  },

  getSupportedCities: async () => {
    try {
      const response = await api.get('/companies/translations/supported-cities');
      return response.data.data;
    } catch (error) {
      console.error('Failed to get supported cities:', error);
      throw error;
    }
  }
};

// Chat API
export const chatApi = {
  sendMessage: async (request: ChatRequest): Promise<RawChatResponse> => {
    try {
      const response = await api.post('/ai/chat-assistant', request);

      // Work with a strongly-typed copy of the response payload
      const rawData = response.data as RawChatResponse;

      if (rawData.companies) {
        // Preserve the unmodified companies array
        rawData.rawCompanies = [...rawData.companies];
        // Transform companies for UI consumption
        rawData.companies = rawData.companies.map(transformCompanyData);
      }

      return rawData;
    } catch (error) {
      console.error('Failed to send message:', error);
      throw error;
    }
  },

  resetChat: async (): Promise<void> => {
    try {
      await api.post('/funds/chat/reset');
    } catch (error) {
      console.error('Failed to reset chat:', error);
      throw error;
    }
  },

  /**
   * Retrieve full message history for a given chat by its ID.
   */
  getConversationHistory: async (
    chatId: string
  ): Promise<Array<{ role: 'user' | 'assistant'; content: string; companies?: Company[]; created_at?: string }>> => {
    try {
      const response = await api.get(`/chats/${chatId}`);
      return (response.data.messages || []).map((msg: any) => ({
        role: msg.role,
        content: msg.content,
        companies: (msg.data?.companies_found || []).map(transformCompanyData),
        created_at: msg.created_at,
      }));
    } catch (error) {
      console.error('Failed to load conversation history:', error);
      throw error;
    }
  },
};

// History API (для боковой панели)
export const historyApi = {
  getHistory: async (): Promise<ChatHistoryItem[]> => {
    try {
      // This endpoint remains correct as it fetches the list of all chats.
      const response = await api.get('/chats/');
      
      console.log('Raw response from /chats/ endpoint:', response);
      console.log('Data from /chats/ endpoint (BEFORE MAPPING):', response.data);

      const rawChatItems = Array.isArray(response.data) ? response.data : [];

      return rawChatItems.map((item: any) => {
        // FIX: Use correct field names from backend (snake_case)
        const threadId = item.thread_id || '';
        const assistantId = item.assistant_id || '';
        return {
          id: item.id || threadId || generateId(),
          userPrompt: item.title || 'Untitled Chat',
          aiResponse: [],
          created_at: item.updated_at ? new Date(item.updated_at).toISOString() : new Date().toISOString(),
          threadId: threadId,
          assistantId: assistantId,
        };
      });
    } catch (error) {
      console.error('Failed to load chat history:', error);
      if (axios.isAxiosError(error)) {
        console.error('Axios error response data:', error.response?.data);
        console.error('Axios error status:', error.response?.status);
      }
      throw error; 
    }
  },

  saveHistory: async (item: Omit<ChatHistoryItem, 'aiResponse' | 'id'> & { id?: string; rawAiResponse: any[] }): Promise<void> => {
    try {
      // MODIFIED: Point to the new, correct endpoint and use the new payload structure.
      await api.post('/chats/history', {
        id: item.id, // The chat ID, which might be an existing one to update
        user_prompt: item.userPrompt,
        raw_ai_response: item.rawAiResponse,
        created_at: item.created_at,
        thread_id: item.threadId,
        assistant_id: item.assistantId,
      });
    } catch (error) {
      console.error('Failed to save chat history:', error);
      throw error;
    }
  },

  deleteHistory: async (id: string): Promise<void> => {
    try {
      // MODIFIED: Point to the new, correct endpoint.
      await api.delete(`/chats/${id}`);
    } catch (error) {
      console.error('Failed to delete chat history:', error);
      throw error;
    }
  }
};

// Auth API with proper error handling and state management
export const authApi = {
  login: async (credentials: AuthCredentials): Promise<AuthResponse> => {
    if (!credentials.email || !credentials.password) {
      throw new Error('Email and password are required');
    }

    try {
      const response = await api.post<AuthResponse>('/auth/login', {
        email: credentials.email,
        password: credentials.password
      });

      if (!response.data?.access_token) {
        throw new Error('Invalid response from server: missing access token');
      }

      // Normalize user fields to match frontend interface
      const normalizedResponse: AuthResponse = {
        ...response.data,
        user: {
          id: response.data.user.id,
          email: response.data.user.email,
          full_name: (response.data.user as any).full_name || response.data.user.full_name || '',
          created_at: (response.data.user as any).created_at || (response.data.user as any).created_at || '',
          is_verified: (response.data.user as any).is_verified || (response.data.user as any).is_verified || false,
          is_active: (response.data.user as any).is_active || (response.data.user as any).is_active || false,
        },
      };

      localStorage.setItem('access_token', normalizedResponse.access_token);
      return normalizedResponse;
    } catch (error) {
      localStorage.removeItem('access_token');
      throw error;
    }
  },

  register: async (credentials: AuthCredentials): Promise<AuthResponse> => {
    if (!credentials.email || !credentials.password || !credentials.full_name) {
      throw new Error('Email, password, and full_name are required for registration');
    }

    try {
      // Register user ‒ backend returns AuthResponse with access_token
      const response = await api.post<AuthResponse>('/auth/register', {
        email: credentials.email,
        password: credentials.password,
        full_name: credentials.full_name,
      });

      if (!response.data?.access_token) {
        throw new Error('Invalid response from server: missing access token');
      }

      // Persist access token the same way as login
      localStorage.setItem('access_token', response.data.access_token);

      return response.data;
    } catch (error) {
      localStorage.removeItem('access_token');
      throw error;
    }
  },

  logout: async (): Promise<void> => {
    localStorage.removeItem('access_token');
  },

  getCurrentUser: async (): Promise<User> => {
    try {
      const response = await api.get('/auth/me');
      return response.data;
    } catch (error) {
      console.error('Failed to get current user:', error);
      throw error;
    }
  },

  deleteAccount: async (): Promise<void> => {
    try {
      await api.delete('/auth/delete-account');
    } catch (error) {
      console.error('Failed to delete account:', error);
      throw error;
    }
  },
};

export default api;