FROM node:24.11.1-alpine3.22 AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.29.3-alpine3.22
ENV API_UPSTREAM=http://backend:8000 DEMO_API_TOKEN= MAX_FILE_MB=20
COPY nginx/15-max-body.envsh /docker-entrypoint.d/15-max-body.envsh
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 8080
