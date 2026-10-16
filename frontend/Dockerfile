# Production image: the built SPA served by nginx over TLS, with /api proxied to core-api.
# Build from the repo root: docker compose --profile web up -d --build web

FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Baked into the bundle and the CSP: where browsers reach Keycloak.
ARG VITE_KEYCLOAK_URL=https://localhost:8443
ENV VITE_KEYCLOAK_URL=$VITE_KEYCLOAK_URL
# chmod: files from public/ keep the host's modes (owner-only on some drives); nginx must read them.
RUN npm run build && chmod -R a+rX dist && node scripts/nginx-headers.ts > security-headers.conf

FROM nginx:1.29-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY --from=build /app/security-headers.conf /etc/nginx/snippets/security-headers.conf
# The official image renders templates with the container's environment at start-up.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
