# Base image extending official n8n
FROM n8nio/n8n:latest

# Switch to root to configure filesystem permissions
USER root

# Create custom local files directory and set ownership for the node user
RUN mkdir -p /files && chown -R node:node /files

# Switch back to non-root 'node' user for security
USER node
