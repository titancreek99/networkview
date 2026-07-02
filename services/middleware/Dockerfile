FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir flask==3.0.3 requests==2.32.3
COPY common/ /app/common/
COPY middleware/ /app/middleware/
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/middleware/app.py"]
