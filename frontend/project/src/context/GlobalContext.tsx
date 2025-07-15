import React, { createContext, useContext, useReducer, useEffect, useRef } from 'react';
import { GlobalState, GlobalAction, Company } from '../types/index';
import { authApi, companiesApi } from '@/services/api';

const initialState: GlobalState = {
  history: [],
  considerationList: [],
  user: null,
  isLoading: true,
};

function globalReducer(state: GlobalState, action: GlobalAction): GlobalState {
  switch (action.type) {
    case 'ADD_HISTORY':
      return {
        ...state,
        history: [action.payload, ...state.history],
      };
    case 'LOAD_HISTORY':
      return {
        ...state,
        history: action.payload,
      };
    case 'DELETE_HISTORY':
      return {
        ...state,
        history: state.history.filter((item) => item.id !== action.payload),
      };
    case 'UPDATE_HISTORY':
      return {
        ...state,
        history: [
          action.payload,
          ...state.history.filter((item) => item.id !== action.payload.id),
        ],
      };
    case 'ADD_CONSIDERATION':
      const isAlreadyAdded = state.considerationList.some(
        (company) => company.bin === action.payload.bin
      );
      if (isAlreadyAdded) return state;
      return {
        ...state,
        considerationList: [...state.considerationList, action.payload],
      };
    case 'REMOVE_CONSIDERATION':
      return {
        ...state,
        considerationList: state.considerationList.filter(
          (company) => company.bin !== action.payload
        ),
      };
    case 'SET_CONSIDERATION_LIST':
      return {
        ...state,
        considerationList: action.payload,
      };
    case 'SET_USER':
      if (action.payload === null) {
        return {
          ...state,
          user: null,
          history: [],
          considerationList: [],
        };
      }
      return {
        ...state,
        user: action.payload,
      };
    case 'SET_LOADING':
      return {
        ...state,
        isLoading: action.payload,
      };
    case 'CLEAR_STATE':
      return {
        ...initialState,
        isLoading: false,
      };
    case 'CLEAR_STATE_PRESERVE_LIST':
      return {
        ...state,
        history: [],
        user: null,
        isLoading: false,
      };
    default:
      return state;
  }
}

interface GlobalContextType {
  state: GlobalState;
  dispatch: React.Dispatch<GlobalAction>;
  addToConsideration: (company: Company) => Promise<void>;
  removeFromConsideration: (bin: string) => Promise<void>;
  isInConsideration: (bin: string) => boolean;
}

const GlobalContext = createContext<GlobalContextType | undefined>(undefined);

export function GlobalProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(globalReducer, initialState);
  const userLoadAttempted = useRef(false);
  const loadRetryCount = useRef(0);
  const maxRetries = 3;

  // Load user on app start only if there's a token
  useEffect(() => {
    let isMounted = true;
    let retryTimeout: NodeJS.Timeout;
    
    const loadUser = async () => {
      const token = localStorage.getItem('access_token');
      if (!token || userLoadAttempted.current) {
        dispatch({ type: 'SET_LOADING', payload: false });
        return;
      }

      try {
        userLoadAttempted.current = true;
        dispatch({ type: 'SET_LOADING', payload: true });
        const user = await authApi.getCurrentUser();
        if (isMounted) {
          dispatch({ type: 'SET_USER', payload: user });
          loadRetryCount.current = 0; // Reset retry count on success
        }
      } catch (error: any) {
        if (isMounted) {
          // ИЗМЕНЕНИЕ: Разлогиниваем пользователя при любой ошибке авторизации (401, 403)
          // или если сервер не может найти пользователя (404).
          const status = error?.response?.status;
          if (status === 401 || status === 403 || status === 404) {
            console.error(`Auth error status ${status}, logging out.`);
            localStorage.removeItem('access_token');
            dispatch({ type: 'SET_USER', payload: null });
          } else if (loadRetryCount.current < maxRetries) {
            // For other errors (network, etc.), retry after a delay
            loadRetryCount.current++;
            retryTimeout = setTimeout(() => {
              userLoadAttempted.current = false; // Reset the attempt flag
              loadUser(); // Retry loading
            }, 2000 * loadRetryCount.current); // Exponential backoff
          }
        }
      } finally {
        if (isMounted) {
          dispatch({ type: 'SET_LOADING', payload: false });
        }
      }
    };

    loadUser();
    
    return () => {
      isMounted = false;
      if (retryTimeout) {
        clearTimeout(retryTimeout);
      }
    };
  }, []);

  // Load consideration list from backend when user changes
  useEffect(() => {
    let isMounted = true;
    const fetchConsiderationList = async () => {
      if (!state.user) {
        dispatch({ type: 'SET_CONSIDERATION_LIST', payload: [] });
        return;
      }
      try {
        const bins = await companiesApi.getConsideration();
        // Fetch company details for each BIN
        const companies: Company[] = await Promise.all(
          bins.map(async (bin) => {
            try {
              return await companiesApi.getDetails(bin);
            } catch (e) {
              // If company not found, skip
              return null;
            }
          })
        ).then(arr => arr.filter(Boolean) as Company[]);
        if (isMounted) {
          dispatch({ type: 'SET_CONSIDERATION_LIST', payload: companies });
        }
      } catch (error) {
        console.error('Failed to load consideration list from backend:', error);
        if (isMounted) {
          dispatch({ type: 'SET_CONSIDERATION_LIST', payload: [] });
        }
      }
    };
    fetchConsiderationList();
    return () => { isMounted = false; };
  }, [state.user]);

  const addToConsideration = async (company: Company) => {
    if (!state.user) return;
    try {
      await companiesApi.addConsideration(company.bin);
      dispatch({ type: 'ADD_CONSIDERATION', payload: company });
    } catch (error) {
      console.error('Failed to add company to consideration:', error);
      throw error;
    }
  };

  const removeFromConsideration = async (bin: string) => {
    if (!state.user) return;
    try {
      await companiesApi.removeConsideration(bin);
      dispatch({ type: 'REMOVE_CONSIDERATION', payload: bin });
    } catch (error) {
      console.error('Failed to remove company from consideration:', error);
      throw error;
    }
  };

  const isInConsideration = (bin: string) => {
    return state.considerationList.some((company) => company.bin === bin);
  };

  return (
    <GlobalContext.Provider
      value={{
        state,
        dispatch,
        addToConsideration,
        removeFromConsideration,
        isInConsideration,
      }}
    >
      {children}
    </GlobalContext.Provider>
  );
}

export const useGlobalContext = () => {
  const context = useContext(GlobalContext);
  if (context === undefined) {
    throw new Error('useGlobalContext must be used within a GlobalProvider');
  }
  return context;
};