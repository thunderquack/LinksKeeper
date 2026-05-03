FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY pyproject.toml README.md ./
COPY linkskeeper ./linkskeeper
COPY static ./static
COPY templates ./templates

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

RUN mkdir -p /data && chown -R appuser:appuser /data /app

USER appuser

EXPOSE 8000

CMD ["gunicorn", "linkskeeper:create_app()", "--bind", "0.0.0.0:8000", "--workers", "2"]

