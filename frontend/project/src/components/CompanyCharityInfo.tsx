import { useState } from "react";
import { Heart, Loader2, AlertCircle, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { CompanyCharityResponse, GoogleSearchResult } from '@/types';

interface CompanyCharityInfoProps {
  companyName: string;
}

export const CompanyCharityInfo = ({ companyName }: CompanyCharityInfoProps) => {
  const [charityData, setCharityData] = useState<CompanyCharityResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchInfo = async () => {
    console.log('🔍 [CHARITY_INFO] Начинаю поиск благотворительности для:', companyName);
    setLoading(true);
    setCharityData(null);
    setError(null);
    
    try {
      const res = await fetch("/api/v1/ai/charity-research", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify({ company_name: companyName }),
      });
      
      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }
      
      const data: CompanyCharityResponse = await res.json();
      console.log('📥 [CHARITY_INFO] Получен ответ:', data);
      setCharityData(data);
      
      if (data.charity_info && data.charity_info.length > 0) {
        console.log(`✅ [CHARITY_INFO] Найдено ${data.charity_info.length} результатов для ${companyName}`);
      } else {
        console.log('ℹ️ [CHARITY_INFO] Релевантных результатов не найдено для', companyName);
      }
    } catch (err) {
      console.error('❌ [CHARITY_INFO] Ошибка при запросе:', err);
      setError('Произошла ошибка при поиске информации о благотворительности');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-3">
      <Button
        onClick={fetchInfo}
        variant="outline"
        size="sm"
        className={`w-full text-xs transition-all duration-200 ${loading ? 'opacity-75 cursor-not-allowed' : 'hover:bg-gray-50'}`}
        disabled={loading}
      >
        {loading ? (
          <>
            <Loader2 className="h-3 w-3 mr-2 animate-spin" />
            Поиск информации...
          </>
        ) : (
          <>
            <Heart className="h-3 w-3 mr-2" />
            Информация о благотворительности
          </>
        )}
      </Button>
      
      {loading && (
        <div className="mt-2 p-3 rounded-md border border-gray-200 bg-gray-50 animate-pulse">
          <div className="flex items-start gap-2">
            <Skeleton className="h-4 w-4 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
              <Skeleton className="h-3 w-2/3" />
            </div>
          </div>
        </div>
      )}
      
      {error && !loading && (
        <div className="mt-2 p-3 rounded-md border border-red-200 bg-red-50 text-xs">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-4 w-4 text-red-600 flex-shrink-0" />
            <div className="text-red-700">{error}</div>
          </div>
        </div>
      )}
      
      {charityData && !loading && !error && (
        <div className="mt-2 space-y-3">
          {/* Сводка */}
          <div className={`p-3 rounded-md border text-xs transition-all duration-300 ease-in-out ${
            charityData.status === 'success' ? 'border-green-200 bg-green-50' : 'border-yellow-200 bg-yellow-50'
          }`}>
            <div className="flex items-start gap-2">
              {charityData.status === 'success' ? (
                <Heart className="h-4 w-4 text-green-600 flex-shrink-0" />
              ) : (
                <AlertCircle className="h-4 w-4 text-yellow-600 flex-shrink-0" />
              )}
              <div className={`flex-1 whitespace-pre-wrap ${
                charityData.status === 'success' ? 'text-green-700' : 'text-yellow-700'
              }`}>
                {charityData.summary}
              </div>
            </div>
          </div>

          {/* Найденные ссылки */}
          {charityData.charity_info && charityData.charity_info.length > 0 && (
            <div className="space-y-2">
              <div className="text-xs font-medium text-gray-700">
                Найдено материалов: {charityData.charity_info.length}
              </div>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {charityData.charity_info.map((item: GoogleSearchResult, index: number) => (
                  <div key={index} className="p-2 bg-white border border-gray-200 rounded text-xs hover:bg-gray-50">
                    <div className="font-medium text-blue-600 mb-1">
                      <a 
                        href={item.link} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="hover:underline flex items-start gap-1"
                      >
                        <span className="flex-1">{item.title}</span>
                        <ExternalLink className="h-3 w-3 flex-shrink-0 mt-0.5" />
                      </a>
                    </div>
                    <div className="text-gray-600 mb-1" style={{
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden'
                    }}>
                      {item.snippet}
                    </div>
                    <div className="text-gray-400 text-xs truncate">
                      {item.link}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}; 