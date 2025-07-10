# frontend/Dockerfile

# --- Этап 1: Сборка React-приложения ---
    FROM node:18-alpine AS build

    WORKDIR /app
    
    # Передаем переменную окружения для API в сборку
    ARG VITE_API_BASE_URL
    ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
    
    # Копируем package.json файлы для установки зависимостей (monorepo-style)
    # Этот шаг кешируется и ускоряет будущие сборки
    COPY package*.json ./
    COPY project/package*.json ./project/
    
    # Устанавливаем все зависимости для корневого проекта и для 'project'
    RUN npm install
    
    # Копируем весь остальной исходный код
    COPY . .
    
    # Запускаем скрипт сборки из корневого package.json
    RUN npm run build
    
    # --- Этап 2: Запуск в Nginx ---
    FROM nginx:1.25-alpine
    
    # --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ---
    # Копируем наш исправленный nginx.conf из контекста сборки (папка frontend)
    # в папку конфигураций Nginx внутри контейнера.
    COPY nginx.conf /etc/nginx/conf.d/default.conf
    
    # Копируем собранные статические файлы из этапа сборки
    # Путь /app/project/dist правильный, так как `npm run build` собирает проект в эту папку.
    COPY --from=build /app/project/dist /usr/share/nginx/html
    
    # Открываем порт 80, который слушает Nginx
    EXPOSE 80
    
    # Команда для запуска Nginx в "не фоновом" режиме
    CMD ["nginx", "-g", "daemon off;"]