FROM python:3.9.20-slim

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD streamlit run main.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true
