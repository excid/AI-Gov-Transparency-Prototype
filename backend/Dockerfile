FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 poppler-utils tesseract-ocr tesseract-ocr-tha tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
COPY ai_gov_transparency ./ai_gov_transparency
RUN pip install --no-cache-dir .
COPY data/models ./data/models
EXPOSE 8000
CMD ["uvicorn", "ai_gov_transparency.service:app", "--host", "0.0.0.0", "--port", "8000"]
