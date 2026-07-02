FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir flask==3.0.3 requests==2.32.3 psycopg2-binary==2.9.9
COPY common/ /app/common/
COPY backend/ /app/backend/
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/backend/app.py"]
