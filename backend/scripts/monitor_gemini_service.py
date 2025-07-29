#!/usr/bin/env python3
"""
Monitoring script for Gemini AI service.
Checks service status, circuit breaker state, and can reset the circuit breaker.
"""

import requests
import json
import time
import sys
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"  # Adjust if your service runs on different port
API_ENDPOINTS = {
    "status": f"{BASE_URL}/ai/status",
    "health_check": f"{BASE_URL}/ai/health-check",
    "reset_circuit_breaker": f"{BASE_URL}/ai/reset-circuit-breaker"
}

def print_status(status_data: Dict[str, Any]):
    """Pretty print the service status."""
    print("\n" + "="*60)
    print("🔍 GEMINI AI SERVICE STATUS")
    print("="*60)
    
    data = status_data.get("data", {})
    
    # Circuit breaker state
    state = data.get("circuit_breaker_state", "UNKNOWN")
    state_emoji = {
        "CLOSED": "🟢",
        "OPEN": "🔴", 
        "HALF_OPEN": "🟡"
    }.get(state, "❓")
    
    print(f"{state_emoji} Circuit Breaker State: {state}")
    
    # Failure count
    failures = data.get("circuit_breaker_failures", 0)
    threshold = data.get("circuit_breaker_threshold", 5)
    print(f"📊 Failures: {failures}/{threshold}")
    
    # Time since last failure
    time_since = data.get("time_since_last_failure")
    if time_since is not None:
        print(f"⏰ Time since last failure: {time_since:.1f} seconds")
    else:
        print("⏰ Time since last failure: Never")
    
    print("="*60)

def check_service_status() -> Dict[str, Any]:
    """Check the current service status."""
    try:
        response = requests.get(API_ENDPOINTS["status"], timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error checking service status: {e}")
        return None

def force_health_check() -> Dict[str, Any]:
    """Force a health check of the Gemini API."""
    try:
        response = requests.post(API_ENDPOINTS["health_check"], timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error during health check: {e}")
        return None

def reset_circuit_breaker() -> Dict[str, Any]:
    """Reset the circuit breaker to CLOSED state."""
    try:
        response = requests.post(API_ENDPOINTS["reset_circuit_breaker"], timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error resetting circuit breaker: {e}")
        return None

def monitor_continuously(interval: int = 30):
    """Continuously monitor the service status."""
    print(f"🔄 Starting continuous monitoring (checking every {interval} seconds)")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            status = check_service_status()
            if status:
                print_status(status)
                
                # Check if circuit breaker is open
                data = status.get("data", {})
                if data.get("circuit_breaker_state") == "OPEN":
                    print("⚠️  Circuit breaker is OPEN! Consider resetting it.")
                
            else:
                print("❌ Could not retrieve service status")
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped by user")

def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python monitor_gemini_service.py status")
        print("  python monitor_gemini_service.py health-check")
        print("  python monitor_gemini_service.py reset")
        print("  python monitor_gemini_service.py monitor [interval_seconds]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "status":
        status = check_service_status()
        if status:
            print_status(status)
        else:
            sys.exit(1)
    
    elif command == "health-check":
        print("🔍 Forcing health check...")
        result = force_health_check()
        if result:
            print(f"✅ Health check result: {result.get('message', 'Unknown')}")
            if result.get("data", {}).get("is_healthy"):
                print("🟢 Gemini API is healthy")
            else:
                print("🔴 Gemini API is unhealthy")
        else:
            print("❌ Health check failed")
            sys.exit(1)
    
    elif command == "reset":
        print("🔄 Resetting circuit breaker...")
        result = reset_circuit_breaker()
        if result:
            print("✅ Circuit breaker reset successfully")
            print_status(result)
        else:
            print("❌ Failed to reset circuit breaker")
            sys.exit(1)
    
    elif command == "monitor":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        monitor_continuously(interval)
    
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main() 