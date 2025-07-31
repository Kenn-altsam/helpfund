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
import { Company, ChatHistoryItem, User, ChatRequest, ChatResponse, AuthCredentials, AuthResponse, CompanyCharityRequest, CompanyCharityResponse } from '@/types';
import { generateId } from '@/lib/utils';

declare global {
  interface ImportMetaEnv {
    readonly VITE_API_BASE_URL: string;
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

// Create axios instance with proper type annotations
const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true, // For http-only cookies
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request deduplication to prevent multiple concurrent requests
const pendingRequests = new Map<string, Promise<any>>();

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

// Response interceptor for better error handling
api.interceptors.response.use(
  (response: AxiosResponse) => {
    return response;
  },
  async (error: AxiosError) => {
    // Handle "Could not validate credentials" error globally
    if (error.response?.status === 401 && (error.response?.data as any)?.detail === "Could not validate credentials") {
      // Clear the invalid token
      localStorage.removeItem('access_token');
      
      // Import toast dynamically to avoid circular dependencies
      const { toast } = await import('sonner');
      
      // Get current language for proper error message
      const currentLang = localStorage.getItem('i18nextLng') || 'en';
      let message = 'Session expired. Please login again.';
      
      if (currentLang === 'ru') {
        message = 'Сессия истекла. Пожалуйста, войдите снова.';
      } else if (currentLang === 'kz') {
        message = 'Сессия аяқталды. Қайта кіріңіз.';
      }
      
      toast.error(message, { duration: 4000 });
      
      // Redirect to login page if not already there
      if (window.location.pathname !== '/auth') {
        window.location.href = '/auth';
      }
    }
    
    if (error.response?.status === 429) {
      const retryAfter = error.response.headers['retry-after'];
      const waitTime = retryAfter ? parseInt(retryAfter) * 1000 : 5000;
      
      console.warn(`Rate limit exceeded. Waiting ${waitTime}ms before retry.`);
      
      // Wait and retry once
      await new Promise(resolve => setTimeout(resolve, waitTime));
      
      // Retry the original request
      if (error.config) {
        return api.request(error.config);
      }
    }
    
    return Promise.reject(error);
  }
);

// Helper function to create unique request keys
const createRequestKey = (method: string, url: string, data?: any): string => {
  return `${method}:${url}:${JSON.stringify(data || {})}`;
};

// Helper function to deduplicate requests
const deduplicateRequest = async <T>(
  key: string,
  requestFn: () => Promise<T>
): Promise<T> => {
  if (pendingRequests.has(key)) {
    console.log(`Request deduplication: reusing pending request for ${key}`);
    return pendingRequests.get(key)!;
  }

  const promise = requestFn().finally(() => {
    pendingRequests.delete(key);
  });
  
  pendingRequests.set(key, promise);
  return promise;
};

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

// Using generateId from utils

// Companies API
export const companiesApi = {
  search: async (params: { location?: string; company_name?: string; limit?: number; page?: number }) => {
    try {
      const response = await api.get('/v1/companies/search', { params });
      return {
        companies: response.data.data.map(transformCompanyData),
        pagination: response.data.metadata?.pagination
      };
    } catch (error) {
      console.error('Failed to search companies:', error);
      throw error;
    }
  },

  getByLocation: async (location: string, limit: number = 50, page: number = 1) => {
    try {
      const response = await api.get(`/v1/companies/by-location/${encodeURIComponent(location)}`, {
        params: { limit, page }
      });
      return {
        companies: response.data.data.map(transformCompanyData),
        pagination: response.data.metadata?.pagination
      };
    } catch (error) {
      console.error('Failed to get companies by location:', error);
      throw error;
    }
  },

  getDetails: async (companyId: string) => {
    try {
      const response = await api.get(`/v1/companies/${companyId}`);
      return transformCompanyData(response.data.data);
    } catch (error) {
      console.error('Failed to get company details:', error);
      throw error;
    }
  },

  getLocations: async () => {
    try {
      const response = await api.get('/v1/companies/locations/list');
      return response.data.data;
    } catch (error) {
      console.error('Failed to get locations:', error);
      throw error;
    }
  },

  getTaxData: async (binNumber: string) => {
    try {
      const response = await api.get(`/v1/companies/tax/${binNumber}`);
      return response.data.data;
    } catch (error) {
      console.error('Failed to get tax data:', error);
      throw error;
    }
  },

  translateCity: async (cityName: string) => {
    try {
      const response = await api.post('/v1/companies/translations/translate-city', null, {
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
      const response = await api.get('/v1/companies/translations/supported-cities');
      return response.data.data;
    } catch (error) {
      console.error('Failed to get supported cities:', error);
      throw error;
    }
  },

  // --- Consideration Endpoints ---
  getConsideration: async (): Promise<string[]> => {
    try {
      const response = await api.get('/v1/companies/consideration');
      return response.data;
    } catch (error) {
      console.error('Failed to get consideration list:', error);
      throw error;
    }
  },

  addConsideration: async (companyBin: string): Promise<void> => {
    try {
      await api.post(`/v1/companies/consideration/${companyBin}`);
    } catch (error) {
      console.error('Failed to add company to consideration:', error);
      throw error;
    }
  },

  removeConsideration: async (companyBin: string): Promise<void> => {
    try {
      await api.delete(`/v1/companies/consideration/${companyBin}`);
    } catch (error) {
      console.error('Failed to remove company from consideration:', error);
      throw error;
    }
  },
};

// Chat API
export const chatApi = {
  sendMessage: async (request: ChatRequest): Promise<RawChatResponse> => {
    const requestKey = createRequestKey('POST', '/v1/ai/chat', request);
    
    return deduplicateRequest(requestKey, async () => {
      try {
        // ИСПРАВЛЕНИЕ: Убираем history из запроса, бэкенд сам загружает из БД
        const cleanRequest = {
          user_input: request.user_input,
          chat_id: request.chat_id, // Используем chat_id вместо thread_id
          // НЕ отправляем history - бэкенд загружает из БД
        };

        const response = await api.post('/v1/ai/chat', cleanRequest);

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
        
        // Handle specific error types
        if (axios.isAxiosError(error)) {
          if (error.response?.status === 429) {
            throw new Error('Rate limit exceeded. Please wait a moment before trying again.');
          } else if (error.response?.status === 503) {
            throw new Error('Service temporarily unavailable. Please try again later.');
          } else if (error.response?.data?.detail) {
            throw new Error(error.response.data.detail);
          }
        }
        
        throw error;
      }
    });
  },

  resetChat: async (): Promise<void> => {
    try {
      await api.post('/v1/funds/chat/reset');
    } catch (error) {
      console.error('Failed to reset chat:', error);
      throw error;
    }
  },

  /**
   * Retrieve full message history for a given chat by its ID using new AI endpoint.
   */
  getConversationHistory: async (
    chatId: string
  ): Promise<Array<{ role: 'user' | 'assistant'; content: string; companies?: Company[]; created_at?: string }>> => {
    const requestKey = createRequestKey('GET', `/v1/ai/chat/${chatId}/history`);
    
    return deduplicateRequest(requestKey, async () => {
      try {
        // ИСПРАВЛЕНИЕ: Используем новый AI эндпоинт для получения истории
        const response = await api.get(`/v1/ai/chat/${chatId}/history`);
        const historyData = response.data.history || [];
        
        return historyData.map((msg: any) => ({
          role: msg.role,
          content: msg.content,
          companies: (msg.companies || []).map(transformCompanyData),
          created_at: msg.created_at,
        }));
      } catch (error) {
        console.error('Failed to load conversation history:', error);
        throw error;
      }
    });
  },
};

// History API (для боковой панели)
export const historyApi = {
  getHistory: async (): Promise<ChatHistoryItem[]> => {
    try {
      // Загружаем список всех чатов для боковой панели
      const response = await api.get('/v1/chats/');
      
      console.log('Raw response from /chats/ endpoint:', response);
      console.log('Data from /chats/ endpoint (BEFORE MAPPING):', response.data);

      const rawChatItems = Array.isArray(response.data) ? response.data : [];

      return rawChatItems.map((item: any) => {
        // Используем правильные имена полей от бэкенда
        const threadId = item.thread_id || '';
        const assistantId = item.assistant_id || '';
        return {
          id: item.id || generateId(),
          userPrompt: item.title || 'Untitled Chat',
          aiResponse: [], // Не загружаем компании в список чатов
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

  // УБИРАЕМ saveHistory - история теперь автоматически сохраняется на бэкенде
  // при каждом сообщении через /ai/chat

  deleteHistory: async (id: string): Promise<void> => {
    try {
      // Удаляем чат через существующий эндпоинт
      await api.delete(`/v1/chats/${id}`);
    } catch (error) {
      console.error('Failed to delete chat history:', error);
      throw error;
    }
  }
};

// Charity Research API
export const charityApi = {
  researchCompany: async (request: CompanyCharityRequest): Promise<CompanyCharityResponse> => {
    try {
      const response = await api.post('/v1/ai/charity-research', request);
      return response.data;
    } catch (error) {
      console.error('Failed to research company charity info:', error);
      throw error;
    }
  },
};

// Auth API with proper error handling and state management
export const authApi = {
  login: async (credentials: AuthCredentials): Promise<AuthResponse> => {
    if (!credentials.email || !credentials.password) {
      throw new Error('Email and password are required');
    }

    try {
      const response = await api.post<AuthResponse>('/v1/auth/login', {
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
      const response = await api.post<AuthResponse>('/v1/auth/register', {
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
      const response = await api.get('/v1/auth/me');
      return response.data;
    } catch (error) {
      console.error('Failed to get current user:', error);
      throw error;
    }
  },

  deleteAccount: async (): Promise<void> => {
    try {
      await api.delete('/v1/auth/delete-account');
    } catch (error) {
      console.error('Failed to delete account:', error);
      throw error;
    }
  },
};

export default api;