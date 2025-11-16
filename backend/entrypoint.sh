#!/bin/sh
set -e

# NINCS useradd, NINCS groupadd, nincs PUID/PGID kezelés
# A konténer már eleve appuser-ként fut (Dockerfile intézi)

cd /app

exec uvicorn main:app --host 0.0.0.0 --port 6100
