FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system ob4scate \
    && useradd --system --gid ob4scate --home-dir /app ob4scate

COPY requirements.txt ./requirements.txt
RUN python -m pip install --requirement requirements.txt

COPY --chown=ob4scate:ob4scate . .
RUN mkdir -p /app/.data /app/logs \
    && chown -R ob4scate:ob4scate /app/.data /app/logs

USER ob4scate

EXPOSE 8000

CMD ["uvicorn", "gateway_proxy.main:app", "--host", "0.0.0.0", "--port", "8000"]
