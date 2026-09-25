FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY packages packages/
COPY drivers drivers/
COPY apps apps/
COPY web web/
COPY marketplace marketplace/
RUN pip install --no-cache-dir -e .
ENV PYTHONPATH=/app/packages:/app/drivers:/app/apps DB_PATH=/data/dealradar.db
VOLUME /data
EXPOSE 8099
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8099", "--app-dir", "apps"]
