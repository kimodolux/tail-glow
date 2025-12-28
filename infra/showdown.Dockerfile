FROM node:18-alpine

# Install git
RUN apk add --no-cache git

# Clone Pokemon Showdown
RUN git clone https://github.com/smogon/pokemon-showdown.git /pokemon-showdown

WORKDIR /pokemon-showdown

# Install dependencies
RUN npm install

# Copy example config
RUN cp config/config-example.js config/config.js

# Give bot users voice rank so they can chat in moderated rooms
RUN echo '{"tailglow1": "+", "tailglow2": "+"}' > config/usergroups.json

# Patch chat.ts to allow unregistered users to chat in battle rooms
# Changes the check from "user.registered || user.autoconfirmed" to "true"
RUN sed -i 's/!(user.registered || user.autoconfirmed)/false/g' server/chat.ts

# Expose the default port
EXPOSE 8000

# Start with --no-security for bot training (disables rate limiting)
CMD ["node", "pokemon-showdown", "start", "--no-security"]
