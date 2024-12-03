FROM python:3.12-slim AS builder
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install pip -U \
    && pip wheel --wheel-dir /app/wheels -r requirements.txt

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
WORKDIR /app
COPY --from=builder /app/wheels /wheels
COPY . .
RUN pip install pip -U \
    && pip install --no-cache-dir /wheels/*
RUN apt-get update && apt-get install --no-install-recommends -y ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8080", "--server.address=0.0.0.0"]
