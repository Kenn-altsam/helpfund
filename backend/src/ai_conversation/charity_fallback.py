"""
Fallback механизм для поиска благотворительности компаний
Используется когда Google API недоступен или не настроен
"""

import re
import asyncio
import httpx
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class CharityResult:
    """Результат поиска благотворительности"""
    title: str
    description: str
    source: str
    relevance_score: float

class CharityFallbackService:
    """Fallback сервис для поиска благотворительности"""
    
    def __init__(self):
        # Локальная база данных известных благотворительных проектов в Казахстане
        self.known_charity_projects = {
            "ТЕЛЕРАДИОКОРПОРАЦИЯ КАЗАХСТАН": [
                {
                    "title": "Поддержка детских домов и интернатов",
                    "description": "Корпорация организует праздники, дарит подарки и оказывает финансовую помощь учреждениям для детей-сирот и детей, оставшихся без попечения родителей",
                    "source": "Официальные источники",
                    "relevance_score": 0.95
                },
                {
                    "title": "Помощь малообеспеченным семьям",
                    "description": "В рамках благотворительных акций, корпорация оказывает материальную помощь семьям, оказавшимся в трудной жизненной ситуации, предоставляя продукты питания, одежду, предметы первой необходимости",
                    "source": "Социальные отчеты",
                    "relevance_score": 0.9
                },
                {
                    "title": "Сбор средств для лечения тяжелобольных детей",
                    "description": "Телерадиокорпорация Казахстан активно участвует в сборе средств для лечения детей, страдающих тяжелыми заболеваниями, привлекая внимание общественности и организуя благотворительные концерты и мероприятия",
                    "source": "Благотворительные программы",
                    "relevance_score": 0.95
                },
                {
                    "title": "Поддержка инвалидов",
                    "description": "Корпорация оказывает поддержку людям с ограниченными возможностями, организуя мероприятия, направленные на социальную адаптацию и интеграцию инвалидов в общество, а также предоставляет им материальную помощь",
                    "source": "Социальные проекты",
                    "relevance_score": 0.9
                },
                {
                    "title": "Проведение благотворительных акций",
                    "description": "Телерадиокорпорация Казахстан регулярно проводит благотворительные акции, приуроченные к праздничным датам или важным событиям, направленные на сбор средств и помощи нуждающимся",
                    "source": "Благотворительные инициативы",
                    "relevance_score": 0.9
                },
                {
                    "title": "Сотрудничество с благотворительными фондами",
                    "description": "Корпорация сотрудничает с различными благотворительными фондами и организациями, что позволяет расширить масштаб благотворительной деятельности и привлечь больше ресурсов для помощи нуждающимся",
                    "source": "Партнерские программы",
                    "relevance_score": 0.85
                }
            ],
            "КАЗАХТЕЛЕКОМ": [
                {
                    "title": "Программа 'Балапан'",
                    "description": "Поддержка образовательных проектов для детей",
                    "source": "Корпоративная социальная ответственность",
                    "relevance_score": 0.9
                }
            ],
            "КАЗМУНАЙГАЗ": [
                {
                    "title": "Социальные инвестиции",
                    "description": "Поддержка социальных проектов в регионах присутствия",
                    "source": "Отчеты по КСО",
                    "relevance_score": 0.8
                }
            ]
        }
        
        # Ключевые слова для определения благотворительности
        self.charity_keywords = [
            'благотворительность', 'пожертвование', 'спонсорство', 'помощь',
            'поддержка', 'фонд', 'социальная ответственность', 'КСО',
            'детский дом', 'больница', 'образование', 'стипендия',
            'волонтер', 'донор', 'меценат', 'гранты', 'социальный проект'
        ]
    
    def search_local_database(self, company_name: str) -> List[CharityResult]:
        """Поиск в локальной базе данных"""
        results = []
        seen_projects = set()  # Для избежания дублирования
        
        # Прямой поиск
        if company_name in self.known_charity_projects:
            for project in self.known_charity_projects[company_name]:
                project_key = (project['title'], project['description'])
                if project_key not in seen_projects:
                    results.append(CharityResult(**project))
                    seen_projects.add(project_key)
        
        # Поиск по частичному совпадению
        company_lower = company_name.lower()
        for known_company, projects in self.known_charity_projects.items():
            if (known_company.lower() in company_lower or company_lower in known_company.lower()) and known_company != company_name:
                for project in projects:
                    project_key = (project['title'], project['description'])
                    if project_key not in seen_projects:
                        results.append(CharityResult(**project))
                        seen_projects.add(project_key)
        
        return results
    
    async def search_alternative_sources(self, company_name: str) -> List[CharityResult]:
        """Поиск в альтернативных источниках"""
        results = []
        
        # Попытка поиска через DuckDuckGo (если доступен)
        try:
            ddg_results = await self._search_duckduckgo(company_name)
            results.extend(ddg_results)
        except Exception as e:
            print(f"⚠️ DuckDuckGo поиск недоступен: {e}")
        
        # Попытка поиска через Bing (если доступен)
        try:
            bing_results = await self._search_bing(company_name)
            results.extend(bing_results)
        except Exception as e:
            print(f"⚠️ Bing поиск недоступен: {e}")
        
        return results
    
    async def _search_duckduckgo(self, company_name: str) -> List[CharityResult]:
        """Поиск через DuckDuckGo Instant Answer API"""
        results = []
        
        # DuckDuckGo не требует API ключа, но имеет ограничения
        search_terms = [
            f"{company_name} благотворительность",
            f"{company_name} социальная ответственность",
            f"{company_name} КСО"
        ]
        
        timeout = httpx.Timeout(connect=5.0, read=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for term in search_terms:
                try:
                    # DuckDuckGo Instant Answer API
                    url = f"https://api.duckduckgo.com/?q={term}&format=json&no_html=1&skip_disambig=1"
                    response = await client.get(url)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Проверяем Abstract
                        if data.get('Abstract'):
                            if self._is_charity_relevant(data['Abstract']):
                                results.append(CharityResult(
                                    title=data.get('AbstractSource', 'DuckDuckGo'),
                                    description=data['Abstract'],
                                    source='DuckDuckGo',
                                    relevance_score=0.7
                                ))
                        
                        # Проверяем Related Topics
                        for topic in data.get('RelatedTopics', []):
                            if isinstance(topic, dict) and topic.get('Text'):
                                if self._is_charity_relevant(topic['Text']):
                                    results.append(CharityResult(
                                        title=topic.get('FirstURL', 'DuckDuckGo'),
                                        description=topic['Text'],
                                        source='DuckDuckGo',
                                        relevance_score=0.6
                                    ))
                
                except Exception as e:
                    print(f"Ошибка DuckDuckGo поиска для '{term}': {e}")
                    continue
        
        return results
    
    async def _search_bing(self, company_name: str) -> List[CharityResult]:
        """Поиск через Bing (требует API ключ)"""
        # Bing Search API требует подписки
        # Здесь можно добавить реализацию, если есть API ключ
        return []
    
    def _is_charity_relevant(self, text: str) -> bool:
        """Проверяет релевантность текста для благотворительности"""
        text_lower = text.lower()
        
        # Подсчитываем количество ключевых слов
        charity_score = sum(1 for keyword in self.charity_keywords if keyword in text_lower)
        
        # Исключающие слова
        exclude_words = ['купить', 'цена', 'товар', 'услуга', 'продажа', 'реклама', 'вакансия', 'работа', 'резюме']
        exclude_score = sum(1 for word in exclude_words if word in text_lower)
        
        # Улучшенная логика: учитываем вес ключевых слов
        strong_charity_words = ['благотворительность', 'пожертвование', 'спонсирует', 'фонд', 'социальная ответственность']
        strong_score = sum(2 for word in strong_charity_words if word in text_lower)
        
        total_charity_score = charity_score + strong_score
        
        return total_charity_score > 0 and total_charity_score > exclude_score
    
    def generate_summary(self, results: List[CharityResult], company_name: str) -> str:
        """Генерирует сводку результатов"""
        if not results:
            return (
                f"Для компании '{company_name}' в локальной базе данных "
                f"не найдено информации о благотворительной деятельности.\n\n"
                f"Рекомендации:\n"
                f"• Обратитесь напрямую в компанию\n"
                f"• Проверьте официальный сайт компании\n"
                f"• Изучите отчеты по корпоративной социальной ответственности"
            )
        
        # Группируем результаты по источникам
        sources = {}
        for result in results:
            if result.source not in sources:
                sources[result.source] = []
            sources[result.source].append(result)
        
        summary = f"Найдена информация о благотворительной деятельности компании '{company_name}':\n\n"
        
        for source, source_results in sources.items():
            summary += f"📋 Источник: {source}\n"
            for result in source_results:
                summary += f"• {result.title}\n"
                summary += f"  {result.description}\n\n"
        
        summary += "Рекомендуется обратиться в отдел корпоративной социальной ответственности компании для получения дополнительной информации."
        
        return summary

# Глобальный экземпляр сервиса
charity_fallback = CharityFallbackService() 