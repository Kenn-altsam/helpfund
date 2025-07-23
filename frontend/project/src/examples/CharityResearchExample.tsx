import React from 'react';
import { CharityResearch } from '@/components/CharityResearch';
import { CompanyCharityCard } from '@/components/CompanyCharityCard';
import { useCharityResearch } from '@/hooks/useCharityResearch';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Company } from '@/types';

/**
 * Пример полной интеграции функциональности исследования благотворительности
 * 
 * Включает:
 * 1. Компонент для ручного поиска (CharityResearch)
 * 2. Расширенную карточку компании с кнопкой исследования (CompanyCharityCard)
 * 3. Хук для программного использования API (useCharityResearch)
 */

export const CharityResearchExample: React.FC = () => {
  // Пример использования хука для программного вызова
  const { data, loading, error, researchCompany, clearResults } = useCharityResearch();

  // Пример данных компании
  const exampleCompany: Company = {
    id: '1',
    bin: '123456789012',
    name: 'ТОО "КазМунайГаз"',
    oked: '06100',
    activity: 'Добыча сырой нефти',
    kato: '751110000',
    locality: 'Алматы',
    krp: '1',
    size: 'Крупная',
    tax_data_2023: 15000000,
    tax_data_2024: 18000000,
    contacts: '+7 727 258 00 00',
    website: 'kmg.kz'
  };

  const handleProgrammaticSearch = async () => {
    await researchCompany({
      company_name: 'Казахстан Темир Жолы',
      additional_context: 'железнодорожный транспорт социальная ответственность'
    });
  };

  return (
    <div className="container mx-auto px-4 py-8 space-y-8">
      {/* Заголовок страницы */}
      <div className="text-center">
        <h1 className="text-3xl font-bold mb-4">
          Исследование благотворительности компаний
        </h1>
        <p className="text-gray-600 max-w-2xl mx-auto">
          Полная демонстрация функциональности поиска информации о благотворительной 
          деятельности компаний с использованием Google Search API.
        </p>
      </div>

      {/* 1. Компонент ручного поиска */}
      <section>
        <h2 className="text-2xl font-bold mb-4">1. Ручной поиск</h2>
        <CharityResearch />
      </section>

      {/* 2. Карточка компании с кнопкой исследования */}
      <section>
        <h2 className="text-2xl font-bold mb-4">2. Карточка компании с исследованием</h2>
        <div className="max-w-md">
          <CompanyCharityCard company={exampleCompany} />
        </div>
      </section>

      {/* 3. Программное использование хука */}
      <section>
        <h2 className="text-2xl font-bold mb-4">3. Программное использование API</h2>
        <Card className="p-6">
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-medium mb-2">Пример использования хука useCharityResearch</h3>
              <p className="text-sm text-gray-600 mb-4">
                Этот пример показывает, как вызвать API исследования благотворительности программно.
              </p>
              
              <Button 
                onClick={handleProgrammaticSearch}
                disabled={loading}
                className="mb-4"
              >
                {loading ? 'Исследую...' : 'Исследовать "Казахстан Темир Жолы"'}
              </Button>

              {error && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg mb-4">
                  <p className="text-red-800 text-sm">{error}</p>
                </div>
              )}

              {data && (
                <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                  <h4 className="font-medium text-green-800 mb-2">
                    Результаты для: {data.company_name}
                  </h4>
                  <p className="text-green-700 text-sm mb-2">{data.summary}</p>
                  <p className="text-green-600 text-xs">
                    Найдено результатов: {data.charity_info.length}
                  </p>
                  {data.charity_info.length > 0 && (
                    <Button 
                      onClick={clearResults}
                      variant="outline"
                      size="sm"
                      className="mt-2"
                    >
                      Очистить результаты
                    </Button>
                  )}
                </div>
              )}
            </div>

            {/* Пример кода */}
            <div className="mt-6">
              <h4 className="text-md font-medium mb-2">Пример кода:</h4>
              <pre className="bg-gray-100 p-4 rounded-lg text-sm overflow-x-auto">
{`import { useCharityResearch } from '@/hooks/useCharityResearch';

const MyComponent = () => {
  const { data, loading, error, researchCompany } = useCharityResearch();

  const handleSearch = async () => {
    await researchCompany({
      company_name: 'Название компании',
      additional_context: 'дополнительный контекст'
    });
  };

  return (
    <div>
      <button onClick={handleSearch} disabled={loading}>
        {loading ? 'Исследую...' : 'Исследовать'}
      </button>
      {data && <div>Результаты: {data.charity_info.length}</div>}
      {error && <div>Ошибка: {error}</div>}
    </div>
  );
};`}
              </pre>
            </div>
          </div>
        </Card>
      </section>

      {/* 4. Документация API */}
      <section>
        <h2 className="text-2xl font-bold mb-4">4. Документация API</h2>
        <Card className="p-6">
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-medium">Эндпоинт</h3>
              <code className="bg-gray-100 px-2 py-1 rounded text-sm">
                POST /api/v1/ai/charity-research
              </code>
            </div>

            <div>
              <h3 className="text-lg font-medium">Запрос</h3>
              <pre className="bg-gray-100 p-4 rounded-lg text-sm overflow-x-auto">
{`{
  "company_name": "Название компании",
  "additional_context": "Дополнительный контекст (опционально)"
}`}
              </pre>
            </div>

            <div>
              <h3 className="text-lg font-medium">Ответ</h3>
              <pre className="bg-gray-100 p-4 rounded-lg text-sm overflow-x-auto">
{`{
  "status": "success" | "error",
  "company_name": "Название компании",
  "charity_info": [
    {
      "title": "Заголовок результата",
      "link": "https://example.com",
      "snippet": "Описание результата поиска"
    }
  ],
  "summary": "Сводка результатов поиска"
}`}
              </pre>
            </div>

            <div>
              <h3 className="text-lg font-medium">Требования</h3>
              <ul className="list-disc list-inside text-sm space-y-1">
                <li>Аутентификация: Bearer токен</li>
                <li>Google API ключ настроен в переменных окружения</li>
                <li>Google Custom Search Engine ID настроен</li>
              </ul>
            </div>
          </div>
        </Card>
      </section>
    </div>
  );
}; 