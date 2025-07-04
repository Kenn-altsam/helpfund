# # Build stage
# FROM node:18-alpine as build

# WORKDIR /app

# # Copy package files
# COPY project/package*.json ./

# # Install dependencies
# RUN npm ci

# # Copy project files
# COPY project/ .

# # Build the application
# RUN npm run build

# # Production stage
# FROM nginx:alpine

# # Copy built assets from build stage
# COPY --from=build /app/dist /usr/share/nginx/html

# # Copy nginx configuration if needed
# # COPY nginx.conf /etc/nginx/conf.d/default.conf

# # Expose port 80
# EXPOSE 80

# # Start nginx
# CMD ["nginx", "-g", "daemon off;"] 

# Build stage
# FROM node:18-alpine as build
# WORKDIR /app
# COPY package*.json ./
# RUN npm ci
# COPY . .
# RUN npm run build

# # Production stage
# FROM nginx:alpine
# # Copy the built app from the build stage to NGINX's web server directory
# COPY --from=build /app/dist /usr/share/nginx/html
# # Expose the port NGINX listens on
# EXPOSE 80
# CMD ["nginx", "-g", "daemon off;"]



# Build stage
FROM node:18-alpine AS build

WORKDIR /app

# Копируем ОБА package.json файла и package-lock.json
COPY package*.json ./
COPY project/package*.json ./project/

# Устанавливаем зависимости для ОБЕИХ частей (root и workspace 'project')
RUN npm install

# Копируем все остальные файлы проекта
COPY . .

# Запускаем скрипт сборки из корневого package.json
RUN npm run build

# --- Production Stage ---
FROM nginx:alpine

# Копируем собранные файлы из папки dist ВНУТРИ папки project
COPY --from=build /app/project/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]