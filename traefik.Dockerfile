FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
EXPOSE 8080
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/
COPY streamlit_app.py pyproject.toml uv.lock ./
COPY .streamlit ./.streamlit
RUN uv sync \
    --frozen \
    --no-install-project \
    --compile-bytecode \
    --no-cache \
    --python-preference only-system \
    && rm -f pyproject.toml uv.lock
RUN apt-get update && apt-get install --no-install-recommends -y \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8080", "--server.address=0.0.0.0"]
