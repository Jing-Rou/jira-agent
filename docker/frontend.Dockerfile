# base image -> uses a minimal Node.js environment to keep the container lightweight
FROM node:22-alpine AS build
# The WORKDIR /app sets the working directory inside the container, ensuring that all subsequent commands run inside this folder.  
WORKDIR /app
# copies the contents of the current directory into the /app directory inside the container.
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80