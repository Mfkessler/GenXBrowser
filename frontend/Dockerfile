FROM node:20-alpine AS build-stage
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install
COPY . .

# Build argument for base URL - defaults to "/" for local dev
ARG VITE_BASE_URL="/"
ENV VITE_BASE_URL=${VITE_BASE_URL}

# Build argument for backend API URL
ARG VITE_API_BASE_URL="/api"
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Build argument for data type - "Isoforms" for Transcript terminology, "Genes" for Gene terminology
ARG VITE_DATA_TYPE="Genes"
ENV VITE_DATA_TYPE=${VITE_DATA_TYPE}

# Skips TypeScript strict type-checking for faster builds
RUN npm run build-only

FROM nginx:stable-alpine
COPY --from=build-stage /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
