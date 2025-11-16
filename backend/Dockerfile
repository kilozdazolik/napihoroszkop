FROM python:slim-bookworm

# System deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV TZ=Europe/Budapest \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Create non-root user
RUN if ! getent group app >/dev/null; then \
        groupadd -g 1001 app; \
    fi && \
    if ! getent passwd appuser >/dev/null; then \
        useradd -u 1001 -g app -s /usr/sbin/nologin -d /app appuser; \
    fi

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# Restrict permissions on application and data dir
RUN mkdir -p /app/data && \
    chown -R appuser:app /app && \
    chmod 700 /app/data

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown appuser:app /entrypoint.sh

USER appuser

EXPOSE 6100

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-u", "main.py"]
