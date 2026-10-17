FROM python:3.10-slim
ENV PYTHONUNBUFFERED=1 MPLBACKEND=Agg
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5001
CMD ["gunicorn","-w","1","--worker-class","gthread","--threads","16","-b","0.0.0.0:5001","--timeout","120","app:app"]
