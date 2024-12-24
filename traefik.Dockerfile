FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
EXPOSE 8080
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/
COPY /src pyproject.toml uv.lock ./
RUN uv sync \
    --frozen \
    --compile-bytecode \
    --python-preference only-system \
    && rm -f pyproject.toml uv.lock
RUN apt-get update && apt-get install --no-install-recommends -y \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
# RUN useradd -r -u 999 app --shell /bin/false \
#     && chown -R app:app /app
# USER app
ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8080", "--server.address=0.0.0.0"]
