# Stage 1: build the game client (Vite + React + Three.js)
FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY docker/certs/ /certs/
COPY frontend/package.json frontend/package-lock.json ./
RUN (cat /certs/*.crt > /tmp/extra-ca.crt 2>/dev/null || true) \
 && NODE_EXTRA_CA_CERTS=/tmp/extra-ca.crt npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# Stage 2: nginx serves the static client and forwards /api to PHP-FPM
FROM nginx:1.27-alpine
COPY docker/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
