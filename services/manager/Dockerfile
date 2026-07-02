FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir flask==3.0.3 requests==2.32.3
COPY common/ /app/common/
COPY manager/ /app/manager/
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/manager/app.py"]
