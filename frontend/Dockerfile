# frontend/Dockerfile
# ── Stage 1: Build ─────────────────────────────────────────────────────────────
# Compiles the Vite/React app into a static bundle.
FROM node:18-alpine AS builder

WORKDIR /app

# Install dependencies first (layer is cached unless package.json changes).
COPY package*.json ./
RUN npm ci

# Bake the production API URL into the Vite bundle at build time.
# Override with --build-arg VITE_API_URL=https://… in CI or on your PaaS.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=${VITE_API_URL}
ENV NODE_ENV=production

COPY . .
RUN npm run build

# ── Stage 2: Serve ──────────────────────────────────────────────────────────────
# Serve the static files with a minimal Nginx image — no Node.js at runtime.
FROM nginx:stable-alpine AS runtime

# Copy the compiled bundle from the build stage.
COPY --from=builder /app/dist /usr/share/nginx/html

# Optional: copy a custom nginx config for SPA client-side routing support.
# If you don't have one, Nginx defaults work fine for a CDN-fronted app.
# COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]