import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# --- НАСТРОЙКА ---

# Секретный ключ для подписи токенов. БЕРЕТСЯ ИЗ .env ФАЙЛА!
# Обязательно установи его в .env, иначе будет ошибка.
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# Это схема, которая говорит FastAPI, откуда брать токен (из заголовка Authorization)
# tokenUrl указывает на эндпоинт, где можно получить токен (мы его создадим позже)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# Утилита для хеширования и проверки паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- ФУНКЦИИ ---

def verify_password(plain_password, hashed_password):
    """Проверяет, соответствует ли обычный пароль хешированному."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """Создает хеш из пароля."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Создает новый JWT токен."""
    to_encode = data.copy()
    
    # Устанавливаем срок жизни токена
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    # Кодируем токен с нашим секретным ключом и алгоритмом
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Зависимость для FastAPI: декодирует токен, проверяет его и возвращает payload.
    Именно эту функцию мы будем вставлять в защищенные эндпоинты.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Пытаемся декодировать токен
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Извлекаем id пользователя из токена. Если его нет - ошибка.
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        
        # Здесь в будущем можно будет сделать запрос к БД и вернуть модель пользователя
        # Сейчас просто вернем id
        return {"user_id": user_id}

    except JWTError:
        # Если токен невалидный (неправильная подпись, истек срок и т.д.)
        raise credentials_exception