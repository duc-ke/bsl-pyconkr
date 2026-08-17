FROM node:24.14.0-alpine
WORKDIR /app
COPY neis-server.mjs agent-server.mjs ./
USER node
EXPOSE 9090
CMD ["node", "neis-server.mjs"]
