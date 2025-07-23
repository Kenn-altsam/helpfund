import React, { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card } from '@/components/ui/Card';
import { charityApi } from '@/services/api';
import { CompanyCharityRequest, CompanyCharityResponse, GoogleSearchResult } from '@/types';

interface CharityResearchProps {
  initialCompanyName?: string;
}

export const CharityResearch: React.FC<CharityResearchProps> = ({ initialCompanyName = '' }) => {
  const [companyName, setCompanyName] = useState(initialCompanyName);
  const [additionalContext, setAdditionalContext] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<CompanyCharityResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    if (!companyName.trim()) {
      setError('Пожалуйста, введите название компании');
      return;
    }

    setIsLoading(true);
    setError(null);
    setResults(null);

    try {
      const request: CompanyCharityRequest = {
        company_name: companyName.trim(),
        additional_context: additionalContext.trim() || undefined,
      };

      const response = await charityApi.researchCompany(request);
      setResults(response);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Произошла ошибка при исследовании компании';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !isLoading) {
      handleSearch();
    }
  };

  return (
    <div className="space-y-6">
      {/* Форма поиска */}
      <Card className="p-6">
        <h2 className="text-2xl font-bold mb-4">Исследование благотворительности компаний</h2>
        
        <div className="space-y-4">
          <div>
            <label htmlFor="company-name" className="block text-sm font-medium mb-2">
              Название компании *
            </label>
            <Input
              id="company-name"
              type="text"
              placeholder="Например: КазМунайГаз"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={isLoading}
            />
          </div>

          <div>
            <label htmlFor="additional-context" className="block text-sm font-medium mb-2">
              Дополнительный контекст (опционально)
            </label>
            <Input
              id="additional-context"
              type="text"
              placeholder="Например: образовательные проекты, поддержка спорта"
              value={additionalContext}
              onChange={(e) => setAdditionalContext(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={isLoading}
            />
          </div>

          <Button 
            onClick={handleSearch} 
            disabled={isLoading || !companyName.trim()}
            className="w-full"
          >
            {isLoading ? 'Исследую...' : 'Исследовать благотворительность'}
          </Button>
        </div>
      </Card>

      {/* Сообщение об ошибке */}
      {error && (
        <Card className="p-4 border-red-200 bg-red-50">
          <div className="text-red-800">
            <h3 className="font-medium">Ошибка</h3>
            <p className="text-sm mt-1">{error}</p>
          </div>
        </Card>
      )}

      {/* Результаты */}
      {results && (
        <div className="space-y-4">
          <Card className="p-6">
            <h3 className="text-xl font-bold mb-2">
              Результаты для компании: {results.company_name}
            </h3>
            
            {/* Статус и сводка */}
            <div className={`p-4 rounded-lg mb-4 ${
              results.status === 'success' ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
            }`}>
              <div className={`font-medium ${
                results.status === 'success' ? 'text-green-800' : 'text-red-800'
              }`}>
                {results.status === 'success' ? '✅ Поиск завершен' : '❌ Ошибка поиска'}
              </div>
              <p className={`text-sm mt-2 ${
                results.status === 'success' ? 'text-green-700' : 'text-red-700'
              }`}>
                {results.summary}
              </p>
            </div>

            {/* Найденные результаты поиска */}
            {results.charity_info && results.charity_info.length > 0 && (
              <div>
                <h4 className="text-lg font-medium mb-3">
                  Найдено материалов: {results.charity_info.length}
                </h4>
                
                <div className="space-y-3">
                  {results.charity_info.map((item: GoogleSearchResult, index: number) => (
                    <div key={index} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50">
                      <h5 className="font-medium text-blue-600 hover:text-blue-800">
                        <a 
                          href={item.link} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="hover:underline"
                        >
                          {item.title}
                        </a>
                      </h5>
                      <p className="text-sm text-gray-600 mt-2 line-clamp-3">
                        {item.snippet}
                      </p>
                      <div className="text-xs text-gray-400 mt-2">
                        <a 
                          href={item.link} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="hover:underline"
                        >
                          {item.link}
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Если результатов нет */}
            {results.charity_info && results.charity_info.length === 0 && (
              <div className="text-center py-8 text-gray-500">
                <p>По запросу не найдено информации о благотворительной деятельности.</p>
                <p className="text-sm mt-2">Попробуйте изменить название компании или добавить дополнительный контекст.</p>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}; 