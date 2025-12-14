#!/bin/bash
set -e

# Docker entrypoint script for Shield Tunneling Edge Platform
# Handles dynamic user switching and initialization

# If running as root, switch to tunnel user
if [ "$(id -u)" = "0" ]; then
    # Ensure data/logs directories exist and have correct permissions
    mkdir -p /app/data /app/logs
    chown -R tunnel:tunnel /app/data /app/logs

    # Execute command as tunnel user using gosu
    exec gosu tunnel "$@"
else
    # Already running as non-root user
    exec "$@"
fi
