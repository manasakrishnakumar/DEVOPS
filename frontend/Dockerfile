FROM python:3.10-slim
ENV PYTHONUNBUFFERED=1 MPLBACKEND=Agg SAVE_PLOT_FILES=0
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn","-w","2","-b","0.0.0.0:5000","--timeout","120","app:app"]
