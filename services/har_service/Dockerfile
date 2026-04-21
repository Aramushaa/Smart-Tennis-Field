FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY model ./model
COPY evaluate_model.py ./evaluate_model.py
COPY inspect_model.py ./inspect_model.py
COPY fix_finder.py ./fix_finder.py

CMD ["python", "-m", "app.main"]
