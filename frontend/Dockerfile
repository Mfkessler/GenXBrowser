FROM node:20-alpine AS build-stage
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install
COPY . .

# Build argument for base URL - defaults to "/" for local dev
ARG VITE_BASE_URL="/"
ENV VITE_BASE_URL=${VITE_BASE_URL}

# Optional prefix before /api (empty for root deployments)
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Build argument for data type - "Isoforms" for Transcript terminology, "Genes" for Gene terminology
ARG VITE_DATA_TYPE="Genes"
ENV VITE_DATA_TYPE=${VITE_DATA_TYPE}

# Build argument for allowed hosts (comma-separated) - localhost and 127.0.0.1 are always included
ARG VITE_ALLOWED_HOSTS=""
ENV VITE_ALLOWED_HOSTS=${VITE_ALLOWED_HOSTS}

# Build argument for photo display mode
ARG VITE_PHOTO_DISPLAY_MODE="circular"
ENV VITE_PHOTO_DISPLAY_MODE=${VITE_PHOTO_DISPLAY_MODE}

# Build argument for footer build date; defaults to the UTC build date when unset
ARG VITE_BUILD_DATE=""
ENV VITE_BUILD_DATE=${VITE_BUILD_DATE}

# Skips TypeScript strict type-checking for faster builds
RUN if [ -z "$VITE_BUILD_DATE" ]; then export VITE_BUILD_DATE="$(date -u +%F)"; fi && npm run build-only

FROM nginx:stable-alpine
COPY --from=build-stage /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
