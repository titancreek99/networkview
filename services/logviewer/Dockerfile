FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir flask==3.0.3
COPY common/ /app/common/
COPY logviewer/ /app/logviewer/
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/logviewer/app.py"]
