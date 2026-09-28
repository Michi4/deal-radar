FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu sqlite3 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -r -m app
WORKDIR /app
COPY pyproject.toml README.md ./
COPY packages packages/
COPY drivers drivers/
COPY apps apps/
COPY web web/
COPY web-v2/dist web-v2/dist/
COPY marketplace marketplace/
RUN pip install --no-cache-dir -e .
ENV PYTHONPATH=/app/packages:/app/drivers:/app/apps DB_PATH=/data/dealradar.db
RUN mkdir -p /data && chown app:app /data
VOLUME /data
EXPOSE 8099
USER app
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8099/health',timeout=4)"
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8099", "--app-dir", "apps"]
