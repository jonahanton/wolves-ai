FROM node:22-alpine AS development

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ENV NEXT_TELEMETRY_DISABLED=1

CMD ["npm", "run", "dev"]


FROM node:22-alpine AS builder

WORKDIR /app
COPY --from=development /app/node_modules ./node_modules

COPY package.json package-lock.json ./
COPY next.config.ts tsconfig.json postcss.config.mjs ./
COPY src ./src
COPY scripts ./scripts
COPY public ./public
RUN rm -rf ./public/archive
COPY --from=archive-source / ./public/archive

ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

RUN npm run build


FROM nginx:1.29-alpine AS production

COPY --from=builder /app/out /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
