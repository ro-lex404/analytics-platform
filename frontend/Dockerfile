FROM node:26-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy the Next.js application code
COPY . .

# Run the development server
CMD ["npm", "run", "dev"]