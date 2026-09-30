FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY . .
RUN npx ng build

FROM nginx:1.27-alpine
ENV API_UPSTREAM=http://app_api:8000
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist/ops-console/browser /usr/share/nginx/html
EXPOSE 80
