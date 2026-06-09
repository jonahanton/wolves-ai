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
COPY public ./public

ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

RUN npm run build


FROM gcr.io/distroless/nodejs22-debian12 AS production

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

CMD ["server.js"]
