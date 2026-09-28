# Multi-stage build: compile the Vite app, then serve the static output from a minimal,
# non-root nginx image. Caddy (infra/Caddyfile) fronts this container for automatic HTTPS and
# for reverse-proxying /api and /voice to the backend.

FROM node:22-slim AS builder

WORKDIR /build
COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
# Empty by default: Caddy (infra/Caddyfile) serves the frontend and reverse-proxies /api and
# /voice on the same origin, so the app can call relative paths and needs no build-time API
# host. Override only for a split-origin deployment.
ARG VITE_API_BASE=""
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

COPY --from=builder /build/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://localhost:8080/ || exit 1
