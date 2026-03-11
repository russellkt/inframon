FROM node:20-slim

WORKDIR /app

# Install pi globally, pm2 for process management, and curl for healthcheck
RUN npm install -g @mariozechner/pi pm2 && apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy package files
COPY package.json package-lock.json* ./
COPY tsconfig.server.json ./

# Install dependencies
RUN npm ci

# Copy web-ui app and build it
COPY web-ui-app ./web-ui-app
WORKDIR /app/web-ui-app
RUN npm ci && npm run build
WORKDIR /app

# Copy pi agent configuration (to /root/.pi for root user)
COPY .pi/ /root/.pi/

# Copy source code and build the Express server
COPY src/ ./src/
RUN npm run build:server

# Copy pm2 config
COPY pm2.config.js .

# Expose ports (3000 for web-ui, 3001 for API)
EXPOSE 3000 3001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:3001/health || exit 1

# Run both API server and web-ui
CMD ["pm2-runtime", "start", "pm2.config.js"]
