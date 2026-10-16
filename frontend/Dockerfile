# 构建阶段：安装依赖、类型检查与打包
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_MODE=mock
ENV VITE_API_MODE=${VITE_API_MODE}
RUN npm run build

# 运行阶段：只带静态产物与 nginx 配置
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
