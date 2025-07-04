# # --- Этап 1: Сборка приложения ---
# FROM node:18-alpine AS build

# WORKDIR /app

# # Передаем переменную окружения для API в сборку
# ARG VITE_API_BASE_URL
# ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# # Копируем package.json и устанавливаем зависимости
# # Это кешируется и ускоряет последующие сборки
# COPY package*.json ./
# RUN npm install

# # Копируем все файлы проекта
# COPY . .

# # Запускаем сборку
# RUN npm run build

# # --- Этап 2: Запуск в Nginx ---
# FROM nginx:1.29.0-alpine

# # Копируем наш файл конфигурации Nginx
# COPY --from=build /app/frontend/nginx.conf /etc/nginx/conf.d/default.conf

# # Копируем собранные статические файлы из этапа сборки в папку Nginx
# # ВАЖНО: Уточни путь к папке dist. Если проект в подпапке "project", то путь будет /app/project/dist
# # Если проект в корне, то /app/dist
# COPY --from=build /app/dist /usr/share/nginx/html
# # Если твой проект в подпапке "project", используй эту строку вместо верхней:
# # COPY --from=build /app/project/dist /usr/share/nginx/html

# # Открываем порт 80, который слушает Nginx
# EXPOSE 80

# # Команда для запуска Nginx
# CMD ["nginx", "-g", "daemon off;"]


# # --- Этап 1: Сборка приложения ---
#     FROM node:18-alpine AS build

#     WORKDIR /app
    
#     # Передаем переменную окружения для API в сборку
#     ARG VITE_API_BASE_URL
#     ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
    
#     # Копируем package.json и устанавливаем зависимости
#     # Это кешируется и ускоряет последующие сборки
#     COPY package*.json ./
#     COPY project/package*.json ./project/

#     RUN npm install
    
#     # Копируем все файлы проекта
#     COPY . .
    
#     # Запускаем сборку
#     RUN npm run build
    
#     # --- Этап 2: Запуск в Nginx ---
#     FROM nginx:1.29.0-alpine
    
#     # Копируем наш файл конфигурации Nginx
#     COPY --from=build /app/frontend/nginx.conf /etc/nginx/conf.d/default.conf
    
#     # Копируем собранные статические файлы из этапа сборки в папку Nginx
#     # ВАЖНО: Уточни путь к папке dist. Если проект в подпапке "project", то путь будет /app/project/dist
#     # Если проект в корне, то /app/dist
#     # COPY --from=build /app/dist /usr/share/nginx/html
#     # Если твой проект в подпапке "project", используй эту строку вместо верхней:
#     COPY --from=build /app/project/dist /usr/share/nginx/html
    
#     # Открываем порт 80, который слушает Nginx
#     EXPOSE 80
    
#     # Команда для запуска Nginx
#     CMD ["nginx", "-g", "daemon off;"]


# --- Этап 1: Сборка приложения ---
    FROM node:18-alpine AS build

    WORKDIR /app
    
    # Передаем переменную окружения для API в сборку
    ARG VITE_API_BASE_URL
    ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
    
    # --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ---
    # Копируем ОБА package.json файла ДО установки зависимостей
    # Это позволяет Docker кешировать этот шаг и ускорять будущие сборки
    COPY package*.json ./
    COPY project/package*.json ./project/
    
    # Теперь npm install увидит оба файла и установит ВСЕ зависимости, включая 'vite'
    RUN npm install
    
    # Копируем все остальные файлы проекта (исходный код)
    COPY . .
    
    # Запускаем скрипт сборки из корневого package.json
    # Он выполнит "cd project && npm run build", как и раньше, но теперь 'vite' будет найден
    RUN npm run build
    
    # --- Этап 2: Запуск в Nginx ---
    FROM nginx:1.29.0-alpine
    
    # Копируем наш файл конфигурации Nginx (убедись, что файл frontend/nginx.conf существует)
    # Если ты его еще не создал, вернись к нашему предыдущему сообщению и создай.
    COPY nginx.conf /etc/nginx/conf.d/default.conf
    
    # Копируем собранные статические файлы из этапа сборки в папку Nginx
    # Путь /app/project/dist правильный, потому что сборка происходит в папке 'project'
    COPY --from=build /app/project/dist /usr/share/nginx/html
    
    # Открываем порт 80, который слушает Nginx
    EXPOSE 80
    
    # Команда для запуска Nginx
    CMD ["nginx", "-g", "daemon off;"]