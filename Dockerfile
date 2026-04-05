FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY app/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH="/app/src"

EXPOSE 8000

#CMD ["python", "app/app.py"]

CMD ["gunicorn", "-b", "0.0.0.0:8000", "app.app:app"]