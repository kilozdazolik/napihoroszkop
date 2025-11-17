#!/bin/bash
set -e

PUID="${PUID:-1036}"
PGID="${PGID:-100}"

# Check if group exists, create if not
if ! getent group "$PGID" >/dev/null 2>&1; then
    groupadd -g "$PGID" appgrp
fi
GRP_NAME=$(getent group "$PGID" | cut -d: -f1)

# Check if user exists, create if not
if ! getent passwd "$PUID" >/dev/null 2>&1; then
    useradd -u "$PUID" -g "$PGID" -m appuser
fi
USER_NAME=$(getent passwd "$PUID" | cut -d: -f1)

# Ensure directories exist and set ownership
mkdir -p /app/data
chown -R "$PUID:$PGID" /app/data

echo "========================================="
echo "Horoscope Backend"
echo "========================================="
echo "Configuration:"
echo "  - User: $USER_NAME:$GRP_NAME (UID=$PUID, GID=$PGID)"
echo "  - Port: 6100"
echo "  - Database: /app/data/horoscope.db"
echo "========================================="
echo "Starting application..."
echo "========================================="

# Execute with correct user using gosu
exec gosu "$PUID:$PGID" "$@"
