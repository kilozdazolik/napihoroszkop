FROM python:slim-bookworm

# Rendszerfüggőségek (minimalizálva, de meghagyva a gcc/libpq-dev-et)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tzdata \
        gcc \
        libpq-dev \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Alap környezeti változók
ENV TZ=Europe/Budapest \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Időzóna beállítás
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Nem-root user létrehozása (BUILD IDŐBEN, idempotensen!)
RUN set -eux; \
    if ! getent group app >/dev/null 2>&1; then \
        groupadd -g 1001 app; \
    fi; \
    if ! id -u appuser >/dev/null 2>&1; then \
        useradd -u 1001 -g app -s /usr/sbin/nologin -d /app appuser; \
    fi

# Először a requirements.txt, hogy működjön a layer cache
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Az alkalmazás fájljai
COPY . .

# Adatkönyvtár és jogosultságok
RUN mkdir -p /app/data && \
    chown -R appuser:app /app && \
    chmod 700 /app/data

# Innentől NEM root userrel fut
USER appuser

EXPOSE 6100

# Közvetlenül az uvicorn-t indítjuk – NINCS ENTRYPOINT, NINCS useradd futáskor
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "6100"]
