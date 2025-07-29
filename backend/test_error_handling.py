#!/usr/bin/env python3
"""
Test script for the improved error handling in GeminiService.
"""

import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.ai_conversation.service import GeminiService

async def test_circuit_breaker():
    """Test the circuit breaker functionality."""
    print("🧪 Testing Circuit Breaker Functionality")
    print("=" * 50)
    
    service = GeminiService()
    
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
    
    service = GeminiService()
    
    # Test location extraction
    print("1. Testing location extraction...")
    test_messages = [
        "Найди компании в Алматы",
        "Покажи фирмы в Астане",
        "Ищу предприятия в Караганде",
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
        "Обычное сообщение без ключевых слов"
    ]
    
    for message in test_messages:
        activities = service._extract_activity_fallback(message)
        print(f"   '{message}' -> {activities}")

def test_fallback_messages():
    """Test the fallback message generation."""
    print("\n🧪 Testing Fallback Messages")
    print("=" * 50)
    
    service = GeminiService()
    
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

async def main():
    """Run all tests."""
    print("🚀 Starting Error Handling Tests")
    print("=" * 60)
    
    try:
        # Test circuit breaker
        await test_circuit_breaker()
        
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
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 