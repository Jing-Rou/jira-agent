FROM node:22-alpine AS dependencies
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=dependencies /app/node_modules ./node_modules
COPY frontend/ ./

ARG DJANGO_API_URL=http://backend:8000
ARG NEXT_PUBLIC_API_BASE_URL=
ENV DJANGO_API_URL=$DJANGO_API_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static

USER node
EXPOSE 3000
CMD ["node", "server.js"]
