FROM python:3.10-slim as builder
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

FROM python:3.10-slim
WORKDIR /app
COPY --from=builder /app/wheels /wheels
COPY . .
RUN pip install --no-cache /wheels/*
RUN apt-get update && apt-get install --no-install-recommends -y ffmpeg=7:5.1.4-0+deb12u1 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
HEALTHCHECK CMD curl --fail http://localhost:80/_stcore/health
ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8080", "--server.address=0.0.0.0"]
