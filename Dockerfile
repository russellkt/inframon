FROM node:20-slim

WORKDIR /app

# Install pi globally and pm2 for process management
RUN npm install -g @mariozechner/pi pm2

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci

# Copy web-ui app
COPY web-ui-app ./web-ui-app
WORKDIR /app/web-ui-app
RUN npm ci && npm run build
WORKDIR /app

# Copy pi agent configuration
COPY .pi/ ~/.pi/

# Copy source code
COPY src/ ./src/
COPY pm2.config.js .

# Build web-ui
RUN npm run build

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000', (r) => {if (r.statusCode !== 200) throw new Error(r.statusCode)})"

# Run both agent and web-ui
CMD ["pm2-runtime", "start", "pm2.config.js"]
