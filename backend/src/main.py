"""
Ayala Foundation Backend API

Main FastAPI application entry point for the Ayala Foundation backend.
This service helps charity funds discover companies and sponsorship opportunities.
"""

import os
from typing import List

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os

# --- ИМПОРТЫ ВАШИХ РОУТЕРОВ ---
# Убедитесь, что здесь есть импорт для ai_conversation
from .ai_conversation.router import router as ai_router
from .auth.router import router as auth_router # Пример
from .companies.router import router as companies_router # Пример
from .chats.router import router as chats_router # Пример

app = FastAPI(
    title="Ayala API",
    description="API for Ayala project",
    version="1.0.0"
)

# Настройка CORS (если есть)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Или ваши конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- РЕГИСТРАЦИЯ РОУТЕРОВ ---
# Вот ключевой момент. Убедитесь, что вы "включаете" ai_router.
# FastAPI добавляет префикс /api из-за вашего фронтенда,
# а сам роутер добавляет /ai, поэтому путь становится /api/ai/chat.

# Часто роутеры регистрируют с общим префиксом /api/v1
# Проверьте, как это сделано у вас
api_v1_router = FastAPI()

print("[INIT] Registering routers...")
api_v1_router.include_router(ai_router)
print("[INIT] ai_router registered at /ai")
api_v1_router.include_router(auth_router)
print("[INIT] auth_router registered")
api_v1_router.include_router(companies_router)
print("[INIT] companies_router registered")
api_v1_router.include_router(chats_router)
print("[INIT] chats_router registered")

# И затем главный роутер подключается к основному приложению
# У вас может быть просто app.include_router(ai_router, prefix="/api")
# Это зависит от структуры вашего проекта.
app.include_router(api_v1_router, prefix="/api/v1") # Пример с версионированием
print("[INIT] All routers registered under /api/v1")

@app.on_event("startup")
def on_startup():
    print("🚀 [STARTUP] Ayala API is starting up...")
    print("📋 [STARTUP] Endpoints:")
    print("   • POST /api/v1/ai/chat - AI Chat endpoint")
    print("   • POST /api/v1/ai/charity-research - Company Charity Research")
    print("   • /api/v1/auth/* - Authentication endpoints")
    print("   • /api/v1/companies/* - Company search endpoints")
    print("   • /api/v1/chats/* - Chat history endpoints")
    print("✅ [STARTUP] All routers and middleware initialized.")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"➡️  [REQUEST] {request.method} {request.url.path}")
    response = await call_next(request)
    print(f"⬅️  [RESPONSE] {request.method} {request.url.path} - {response.status_code}")
    return response

@app.get("/health")
def health_check():
    print("❤️ [HEALTH] Health check endpoint accessed")
    """Простая проверка работоспособности сервиса."""
    return {"status": "ok"} 