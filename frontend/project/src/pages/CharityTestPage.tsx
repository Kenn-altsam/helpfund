import React from 'react';
import { CharityResearch } from '@/components/CharityResearch';
import { CompanyCharityCard } from '@/components/CompanyCharityCard';
import { useCharityResearch } from '@/hooks/useCharityResearch';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Company } from '@/types';

export const CharityTestPage: React.FC = () => {
  const { data, loading, error, researchCompany } = useCharityResearch();

  // Пример компаний для тестирования
  const exampleCompanies: Company[] = [
    {
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
    },
    {
      id: '2',
      bin: '210987654321',
      name: 'АО "Казахтелеком"',
      oked: '61100',
      activity: 'Деятельность в области телекоммуникаций',
      kato: '751110000',
      locality: 'Алматы',
      krp: '1',
      size: 'Крупная',
      tax_data_2023: 12000000,
      tax_data_2024: 14000000,
      contacts: '+7 727 258 77 77',
      website: 'telecom.kz'
    }
  ];

  const handleQuickTest = async (companyName: string) => {
    await researchCompany({
      company_name: companyName,
      additional_context: 'образование здравоохранение спорт'
    });
  };

  return (
    <div className="container mx-auto px-4 py-8 space-y-8">
      {/* Заголовок */}
      <div className="text-center">
        <h1 className="text-3xl font-bold mb-4">
          🔍 Тестирование поиска благотворительности
        </h1>
        <p className="text-gray-600">
          Проверьте, как работает поиск информации о благотворительной деятельности компаний
        </p>
      </div>

      {/* Быстрое тестирование */}
      <Card className="p-6">
        <h2 className="text-xl font-bold mb-4">⚡ Быстрое тестирование</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <Button 
            onClick={() => handleQuickTest('КазМунайГаз')}
            disabled={loading}
            variant="outline"
          >
            {loading ? 'Ищу...' : 'Тест: КазМунайГаз'}
          </Button>
          <Button 
            onClick={() => handleQuickTest('Казахтелеком')}
            disabled={loading}
            variant="outline"
          >
            {loading ? 'Ищу...' : 'Тест: Казахтелеком'}
          </Button>
          <Button 
            onClick={() => handleQuickTest('Тенгизшевройл')}
            disabled={loading}
            variant="outline"
          >
            {loading ? 'Ищу...' : 'Тест: Тенгизшевройл'}
          </Button>
        </div>

        {/* Результаты быстрого тестирования */}
        {error && (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <h3 className="font-medium text-red-800">❌ Ошибка:</h3>
            <p className="text-red-600 text-sm mt-1">{error}</p>
          </div>
        )}

        {data && (
          <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
            <h3 className="font-medium text-green-800 mb-2">
              ✅ Результаты для: {data.company_name}
            </h3>
            <p className="text-green-700 text-sm mb-2">{data.summary}</p>
            <div className="text-green-600 text-xs">
              Найдено результатов: {data.charity_info.length}
            </div>
            {data.charity_info.length > 0 && (
              <div className="mt-3">
                <h4 className="text-sm font-medium text-green-800 mb-2">Найденные материалы:</h4>
                <div className="space-y-2">
                  {data.charity_info.slice(0, 3).map((item, index) => (
                    <div key={index} className="text-xs">
                      <a 
                        href={item.link} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline"
                      >
                        {item.title}
                      </a>
                    </div>
                  ))}
                  {data.charity_info.length > 3 && (
                    <div className="text-xs text-gray-500">
                      ... и еще {data.charity_info.length - 3} результатов
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Полный компонент поиска */}
      <Card className="p-6">
        <h2 className="text-xl font-bold mb-4">🔍 Детальный поиск</h2>
        <CharityResearch />
      </Card>

      {/* Карточки компаний с кнопками исследования */}
      <Card className="p-6">
        <h2 className="text-xl font-bold mb-4">🏢 Тестовые карточки компаний</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {exampleCompanies.map((company) => (
            <CompanyCharityCard key={company.id} company={company} />
          ))}
        </div>
      </Card>

      {/* Инструкции */}
      <Card className="p-6 bg-blue-50">
        <h2 className="text-xl font-bold mb-4 text-blue-800">📋 Инструкции по тестированию</h2>
        <div className="text-blue-700 space-y-2">
          <p><strong>1. Быстрое тестирование:</strong> Нажмите одну из кнопок выше для мгновенного поиска</p>
          <p><strong>2. Детальный поиск:</strong> Введите название компании в форму ниже</p>
          <p><strong>3. Карточки компаний:</strong> Нажмите кнопку "Благотворительность" на карточке</p>
          <p><strong>4. Результаты:</strong> Просмотрите найденные ссылки и сводку</p>
        </div>
      </Card>

      {/* Статистика */}
      <Card className="p-6 bg-gray-50">
        <h2 className="text-xl font-bold mb-4">📊 Информация о поиске</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <h3 className="font-medium mb-2">🎯 Что ищем:</h3>
            <ul className="text-gray-600 space-y-1">
              <li>• Благотворительные фонды</li>
              <li>• Социальные программы</li>
              <li>• Спонсорские проекты</li>
              <li>• КСО инициативы</li>
            </ul>
          </div>
          <div>
            <h3 className="font-medium mb-2">🚫 Что фильтруем:</h3>
            <ul className="text-gray-600 space-y-1">
              <li>• Новости и статьи</li>
              <li>• Вакансии</li>
              <li>• Рекламу услуг</li>
              <li>• Прайс-листы</li>
            </ul>
          </div>
          <div>
            <h3 className="font-medium mb-2">🌐 Источники:</h3>
            <ul className="text-gray-600 space-y-1">
              <li>• Google Search API</li>
              <li>• 8 специфичных запросов</li>
              <li>• Фокус на Казахстан</li>
              <li>• Русский + английский</li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  );
}; 