FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY packages packages/
COPY drivers drivers/
COPY apps apps/
COPY web web/
RUN pip install --no-cache-dir -e .
ENV PYTHONPATH=/app/packages:/app/drivers:/app/apps DB_PATH=/data/dealradar.db
VOLUME /data
EXPOSE 8099
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8099", "--app-dir", "apps"]
