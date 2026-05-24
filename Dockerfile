FROM python:3.12-slim

WORKDIR /app

RUN pip install poetry==2.4.1 && \
    poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --only main --no-root

COPY src/ ./src/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

ENTRYPOINT ["python", "-m", "offerlens.cli"]
CMD ["scan", "--query", "python backend", "--limit", "20"]
