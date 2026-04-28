FROM node:20-alpine

# Set the working directory inside the container
WORKDIR /app

# Copy the package.json and package-lock.json first to leverage Docker cache
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application files
COPY . .

# Expose the port Vite runs on
EXPOSE 5173

# Start the Vite development server and expose on all network interfaces
CMD ["npm", "run", "dev", "--", "--host"]
