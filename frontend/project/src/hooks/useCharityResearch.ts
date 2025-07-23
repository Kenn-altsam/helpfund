import { useState } from 'react';
import { charityApi } from '@/services/api';
import { CompanyCharityRequest, CompanyCharityResponse } from '@/types';

interface UseCharityResearchResult {
  data: CompanyCharityResponse | null;
  loading: boolean;
  error: string | null;
  researchCompany: (request: CompanyCharityRequest) => Promise<void>;
  clearResults: () => void;
}

export const useCharityResearch = (): UseCharityResearchResult => {
  const [data, setData] = useState<CompanyCharityResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const researchCompany = async (request: CompanyCharityRequest): Promise<void> => {
    setLoading(true);
    setError(null);
    setData(null);

    try {
      const response = await charityApi.researchCompany(request);
      setData(response);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Произошла ошибка при исследовании компании';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const clearResults = () => {
    setData(null);
    setError(null);
  };

  return {
    data,
    loading,
    error,
    researchCompany,
    clearResults,
  };
}; 