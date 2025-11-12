FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:/root/.deno/bin:$PATH"
EXPOSE 8080
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/
COPY /src pyproject.toml uv.lock ./
RUN uv sync \
    --frozen \
    --no-dev \
    --compile-bytecode \
    --python-preference only-system \
    && rm -f pyproject.toml uv.lock
RUN apt-get update && apt-get install --no-install-recommends -y \
    ffmpeg \
    curl \
    unzip \
    && set -o pipefail && curl -fsSL https://deno.land/install.sh | sh \
    && apt-get purge -y unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
# RUN useradd -r -u 999 app --shell /bin/false \
#     && chown -R app:app /app
# USER app
HEALTHCHECK CMD curl --fail http://localhost:8080/_stcore/health
ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8080", "--server.address=0.0.0.0"]
