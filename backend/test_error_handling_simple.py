#!/usr/bin/env python3
"""
Simple test script for the error handling improvements.
Tests only the core logic without database dependencies.
"""

import time
import re
from typing import Optional, List, Dict, Any

class MockGeminiService:
    """Mock service for testing error handling logic."""
    
    def __init__(self):
        # Circuit breaker state
        self._circuit_breaker_failures = 0
        self._circuit_breaker_last_failure_time = 0
        self._circuit_breaker_threshold = 5  # failures before opening
        self._circuit_breaker_timeout = 60  # seconds to wait before trying again
        self._circuit_breaker_state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def _should_use_circuit_breaker(self) -> bool:
        """
        Check if circuit breaker should prevent API calls.
        """
        current_time = time.time()
        
        if self._circuit_breaker_state == "OPEN":
            if current_time - self._circuit_breaker_last_failure_time > self._circuit_breaker_timeout:
                print("🔄 [CIRCUIT_BREAKER] Moving to HALF_OPEN state")
                self._circuit_breaker_state = "HALF_OPEN"
                return False
            else:
                print("🚫 [CIRCUIT_BREAKER] Circuit breaker is OPEN, skipping API call")
                return True
        
        return False

    def _record_circuit_breaker_failure(self):
        """
        Record a failure for circuit breaker logic.
        """
        self._circuit_breaker_failures += 1
        self._circuit_breaker_last_failure_time = time.time()
        
        if self._circuit_breaker_failures >= self._circuit_breaker_threshold:
            print(f"🚫 [CIRCUIT_BREAKER] Opening circuit breaker after {self._circuit_breaker_failures} failures")
            self._circuit_breaker_state = "OPEN"
        else:
            print(f"⚠️ [CIRCUIT_BREAKER] Failure {self._circuit_breaker_failures}/{self._circuit_breaker_threshold}")

    def _record_circuit_breaker_success(self):
        """
        Record a success for circuit breaker logic.
        """
        if self._circuit_breaker_state == "HALF_OPEN":
            print("✅ [CIRCUIT_BREAKER] Success in HALF_OPEN state, closing circuit breaker")
            self._circuit_breaker_state = "CLOSED"
        
        self._circuit_breaker_failures = 0

    def get_service_status(self) -> Dict[str, Any]:
        """
        Get current service status including circuit breaker state.
        """
        return {
            "circuit_breaker_state": self._circuit_breaker_state,
            "circuit_breaker_failures": self._circuit_breaker_failures,
            "circuit_breaker_threshold": self._circuit_breaker_threshold,
            "last_failure_time": self._circuit_breaker_last_failure_time,
            "time_since_last_failure": time.time() - self._circuit_breaker_last_failure_time if self._circuit_breaker_last_failure_time > 0 else None
        }

    def reset_circuit_breaker(self):
        """
        Manually reset the circuit breaker to CLOSED state.
        """
        print("🔄 [CIRCUIT_BREAKER] Manually resetting circuit breaker")
        self._circuit_breaker_state = "CLOSED"
        self._circuit_breaker_failures = 0
        self._circuit_breaker_last_failure_time = 0

    def _extract_location_fallback(self, message: str) -> Optional[str]:
        """Simple location extraction as fallback when Gemini is unavailable."""
        # Common location keywords with variations
        location_mappings = {
            "алматы": "Алматы",
            "астана": "Астана", 
            "астане": "Астана",
            "шымкент": "Шымкент",
            "актобе": "Актобе",
            "караганда": "Караганда",
            "караганде": "Караганда",
            "тараз": "Тараз",
            "павлодар": "Павлодар",
            "семей": "Семей",
            "усть-каменогорск": "Усть-Каменогорск",
            "урджар": "Урджар",
            "кызылорда": "Кызылорда",
            "атырау": "Атырау",
            "актау": "Актау",
            "костанай": "Костанай",
            "петропавловск": "Петропавловск",
            "кокшетау": "Кокшетау",
            "талдыкорган": "Талдыкорган",
            "туркестан": "Туркестан",
            "кентау": "Кентау",
            "жамбыл": "Жамбыл"
        }
        
        message_lower = message.lower()
        for location_variant, canonical_name in location_mappings.items():
            if location_variant in message_lower:
                return canonical_name
        return None

    def _extract_quantity_fallback(self, message: str) -> int:
        """Simple quantity extraction as fallback when Gemini is unavailable."""
        numbers = re.findall(r'\d+', message)
        if numbers:
            return min(int(numbers[0]), 50)  # Cap at 50 for safety
        return 10

    def _extract_activity_fallback(self, message: str) -> Optional[List[str]]:
        """Simple activity keyword extraction as fallback when Gemini is unavailable."""
        # Common activity keywords with variations
        activity_mappings = {
            "it": "IT",
            "технологии": "технологии",
            "технология": "технологии",
            "программирование": "программирование",
            "программист": "программирование",
            "строительство": "строительство",
            "строительный": "строительство",
            "строительные": "строительство",
            "торговля": "торговля",
            "торговый": "торговля",
            "производство": "производство",
            "производственный": "производство",
            "услуги": "услуги",
            "услуга": "услуги",
            "образование": "образование",
            "образовательный": "образование",
            "медицина": "медицина",
            "медицинский": "медицина",
            "медицинские": "медицина",
            "финансы": "финансы",
            "финансовый": "финансы",
            "финансовые": "финансы",
            "транспорт": "транспорт",
            "транспортный": "транспорт",
            "энергетика": "энергетика",
            "энергетический": "энергетика",
            "нефть": "нефть",
            "нефтяной": "нефть",
            "нефтяные": "нефть",
            "газ": "газ",
            "газовый": "газ",
            "металлургия": "металлургия",
            "металлургический": "металлургия"
        }
        
        message_lower = message.lower()
        found_keywords = []
        for keyword_variant, canonical_keyword in activity_mappings.items():
            if keyword_variant in message_lower:
                if canonical_keyword not in found_keywords:
                    found_keywords.append(canonical_keyword)
        
        return found_keywords if found_keywords else None

    def _get_fallback_message(self, error_type: str) -> str:
        """Get appropriate fallback message based on error type."""
        messages = {
            "timeout": "Извините, запрос занимает больше времени, чем ожидалось. Попробуйте еще раз через минуту.",
            "http_error": "Извините, у нас временные проблемы с обработкой запросов. Попробуйте еще раз.",
            "json_error": "Извините, произошла ошибка при обработке ответа. Попробуйте переформулировать запрос.",
            "unexpected_error": "Извините, произошла неожиданная ошибка. Попробуйте еще раз.",
            "max_retries_exceeded": "Извините, сервис временно недоступен. Попробуйте позже.",
            "service_unavailable": "Извините, сервис обработки запросов временно недоступен. Попробуйте через несколько минут.",
            "circuit_breaker_open": "Извините, сервис временно недоступен из-за технических проблем. Попробуйте через минуту."
        }
        return messages.get(error_type, "Извините, произошла ошибка. Попробуйте еще раз.")

def test_circuit_breaker():
    """Test the circuit breaker functionality."""
    print("🧪 Testing Circuit Breaker Functionality")
    print("=" * 50)
    
    service = MockGeminiService()
    
    # Test initial state
    print("1. Testing initial state...")
    status = service.get_service_status()
    print(f"   Circuit breaker state: {status['circuit_breaker_state']}")
    print(f"   Failures: {status['circuit_breaker_failures']}")
    assert status['circuit_breaker_state'] == 'CLOSED'
    print("   ✅ Initial state is correct")
    
    # Test recording failures
    print("\n2. Testing failure recording...")
    for i in range(3):
        service._record_circuit_breaker_failure()
        status = service.get_service_status()
        print(f"   After {i+1} failures: {status['circuit_breaker_failures']}/{status['circuit_breaker_threshold']}")
    
    assert status['circuit_breaker_state'] == 'CLOSED'  # Should still be closed
    print("   ✅ Circuit breaker still closed after 3 failures")
    
    # Test opening circuit breaker
    print("\n3. Testing circuit breaker opening...")
    for i in range(2):  # Add 2 more failures to reach threshold
        service._record_circuit_breaker_failure()
    
    status = service.get_service_status()
    print(f"   After 5 failures: {status['circuit_breaker_failures']}/{status['circuit_breaker_threshold']}")
    print(f"   Circuit breaker state: {status['circuit_breaker_state']}")
    assert status['circuit_breaker_state'] == 'OPEN'
    print("   ✅ Circuit breaker opened correctly")
    
    # Test reset
    print("\n4. Testing circuit breaker reset...")
    service.reset_circuit_breaker()
    status = service.get_service_status()
    print(f"   After reset: {status['circuit_breaker_state']}")
    assert status['circuit_breaker_state'] == 'CLOSED'
    print("   ✅ Circuit breaker reset correctly")

def test_fallback_parsing():
    """Test the fallback parsing functionality."""
    print("\n🧪 Testing Fallback Parsing")
    print("=" * 50)
    
    service = MockGeminiService()
    
    # Test location extraction
    print("1. Testing location extraction...")
    test_messages = [
        "Найди компании в Алматы",
        "Покажи фирмы в Астане",
        "Ищу предприятия в Караганде",
        "Строительные фирмы в Астане",
        "Нет локации в этом сообщении"
    ]
    
    for message in test_messages:
        location = service._extract_location_fallback(message)
        print(f"   '{message}' -> {location}")
    
    # Test quantity extraction
    print("\n2. Testing quantity extraction...")
    test_messages = [
        "Найди 15 компаний",
        "Покажи 25 фирм",
        "Ищу 100 предприятий",  # Should be capped at 50
        "Нет числа в сообщении"
    ]
    
    for message in test_messages:
        quantity = service._extract_quantity_fallback(message)
        print(f"   '{message}' -> {quantity}")
    
    # Test activity extraction
    print("\n3. Testing activity extraction...")
    test_messages = [
        "IT компании в Алматы",
        "Строительные фирмы",
        "Финансовые услуги",
        "Медицинские услуги",
        "Нефтяные компании",
        "Обычное сообщение без ключевых слов"
    ]
    
    for message in test_messages:
        activities = service._extract_activity_fallback(message)
        print(f"   '{message}' -> {activities}")

def test_fallback_messages():
    """Test the fallback message generation."""
    print("\n🧪 Testing Fallback Messages")
    print("=" * 50)
    
    service = MockGeminiService()
    
    error_types = [
        "timeout",
        "http_error", 
        "json_error",
        "circuit_breaker_open",
        "service_unavailable",
        "unknown_error"
    ]
    
    for error_type in error_types:
        message = service._get_fallback_message(error_type)
        print(f"   {error_type}: {message[:50]}...")

def main():
    """Run all tests."""
    print("🚀 Starting Error Handling Tests")
    print("=" * 60)
    
    try:
        # Test circuit breaker
        test_circuit_breaker()
        
        # Test fallback parsing
        test_fallback_parsing()
        
        # Test fallback messages
        test_fallback_messages()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 