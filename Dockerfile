FROM ghcr.io/prefix-dev/pixi:latest AS build
WORKDIR /app
COPY pyproject.toml pixi.lock ./
COPY src/ src/
RUN pixi install --locked -e docker && pixi clean cache -y

FROM ubuntu:resolute AS production
ENV PATH="/app/.pixi/envs/docker/bin:$PATH"
EXPOSE 8080
WORKDIR /app
COPY --from=build /app/.pixi/envs/docker /app/.pixi/envs/docker
COPY src/ ./
HEALTHCHECK CMD curl --fail http://localhost:8080/_stcore/health
ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8080", "--server.address=0.0.0.0"]
