FROM node:18-alpine

# Install git (required to clone pokemon-showdown)
RUN apk add --no-cache git

# Clone Pokemon Showdown
RUN git clone https://github.com/smogon/pokemon-showdown.git /pokemon-showdown

WORKDIR /pokemon-showdown

# Install dependencies
RUN npm install

# Copy example config
RUN cp config/config-example.js config/config.js

# Expose the default port
EXPOSE 8000

# Start with --no-security for bot training (disables rate limiting)
CMD ["node", "pokemon-showdown", "start", "--no-security"]
