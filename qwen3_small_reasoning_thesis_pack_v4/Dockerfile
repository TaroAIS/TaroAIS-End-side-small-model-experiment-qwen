FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Optional: if you need system deps for faiss/chroma, add apt-get here.

COPY . /app
CMD ["bash", "scripts/run_smoke.sh"]
