FROM python:3.12-slim
WORKDIR /app
COPY apps/worker /app
RUN pip install --no-cache-dir .
CMD ["mapa-ingest", "gobierno"]
