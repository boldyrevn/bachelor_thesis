FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Expose dev server port
EXPOSE 3000

# Default command (dev mode with hot reload)
CMD ["npm", "run", "dev"]
