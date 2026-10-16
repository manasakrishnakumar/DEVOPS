FROM python:3.10-slim
RUN pip install --no-cache-dir kopf==1.37.2 kubernetes==29.0.0 requests==2.31.0
WORKDIR /app
COPY forecast_operator.py .
