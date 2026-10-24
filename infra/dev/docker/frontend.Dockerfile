FROM node:22-bookworm-slim@sha256:de170b39439eb0e5a3444ad7d60b015614a381e10fecae2e30ec9e735122f38d
WORKDIR /workspace/frontend
COPY context-public/repository/frontend/package.json context-public/repository/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY context-public/repository/frontend/ ./
COPY context-public/repository/src/ /workspace/src/
COPY context-public/repository/docs/ /workspace/docs/
RUN chown -R node:node /workspace
COPY --chown=node:node docker/vite.dev.config.mjs ./docker-vite.config.mjs
USER node
ENV BAGO_API_PROXY_TARGET=http://host.docker.internal:8080
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173", "--strictPort", "--config", "docker-vite.config.mjs"]
