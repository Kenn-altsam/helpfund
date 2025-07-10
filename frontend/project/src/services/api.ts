/// <reference types="vite/client" />

import axios, { AxiosResponse, AxiosError, InternalAxiosRequestConfig } from 'axios';
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
  // Format tax information for display
  const formatTaxAmount = (amount?: number) => {
    if (!amount) return '0';
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'KZT',
      maximumFractionDigits: 0
    }).format(amount);
  };

  const taxYears = ['2020', '2021', '2022', '2023', '2024', '2025']
    .map(year => ({
      year,
      amount: company[`tax_${year}`]
    }))
    .filter(tax => tax.amount)
    .map(tax => `${tax.year}: ${formatTaxAmount(tax.amount)}`)
    .join('\n');

  return {
    ...company,
    // Prefer existing fields if already present; otherwise map from backend-specific names
    region: company.region || company.locality,
    industry: company.industry || company.activity,
    taxes: taxYears || 'Нет данных о налогах',
    // These fields might be added by the AI service or other sources
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
   * Retrieve full message history for a given assistant/thread.
   * The backend returns an array of { role: 'user' | 'assistant', content: string }
   */
  getConversationHistory: async (
    _assistantId: string, // currently unused but kept for potential future auth handling
    threadId: string
  ): Promise<Array<{ role: 'user' | 'assistant'; content: string; companies?: Company[] }>> => { // added optional companies field
    try {
      // Unified chat history endpoint for both AI and funds chat
      const response = await api.get(`/funds/chat/thread/${threadId}/history`);

      // Backend returns the history array directly; no additional nesting expected
      return response.data ?? [];
    } catch (error) {
      console.error('Failed to load conversation history:', error);
      throw error;
    }
  },
};

// History API
export const historyApi = {
  getHistory: async (): Promise<ChatHistoryItem[]> => {
    try {
      const response = await api.get('/funds/chat/history');
      return response.data.map((item: any) => ({
        id: item.id,
        userPrompt: item.user_input,
        aiResponse: item.companies_data.map(transformCompanyData),
        created_at: item.created_at,
        threadId: item.thread_id || null,
        assistantId: item.assistant_id || null,
      }));
    } catch (error) {
      console.error('Failed to get chat history:', error);
      throw error;
    }
  },

  saveHistory: async (item: Omit<ChatHistoryItem, 'aiResponse' | 'id'> & { id?: string; rawAiResponse: any[] }): Promise<void> => {
    try {
      await api.post('/funds/chat/history/save', {
        user_input: item.userPrompt,
        companies_data: item.rawAiResponse,
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
      await api.delete(`/funds/chat/history/${id}`);
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
      // First, create the user account (backend expects snake_case full_name)
      await api.post('/api/v1/register', {
        email: credentials.email,
        password: credentials.password,
        full_name: credentials.full_name,
      });

      // Immediately log the user in to obtain an access token
      const loginResponse = await authApi.login({
        email: credentials.email,
        password: credentials.password,
      });

      return loginResponse;
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