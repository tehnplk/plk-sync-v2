FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Bangkok

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends cron tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY docker/cron/plk-sync.cron /etc/cron.d/plk-sync
COPY docker/entrypoint.sh /entrypoint.sh

RUN sed -i 's/\r$//' /entrypoint.sh /etc/cron.d/plk-sync \
    && chmod 0644 /etc/cron.d/plk-sync \
    && chmod +x /entrypoint.sh

ENTRYPOINT ["sh", "/entrypoint.sh"]
