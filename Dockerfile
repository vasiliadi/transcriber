FROM ghcr.io/prefix-dev/pixi:trixie@sha256:65c1174d9c4101bc44fbc1ede6915d8d51eea82053f7a5a8641eb2e7fbdaeb42 AS build
WORKDIR /app
COPY pyproject.toml pixi.lock ./
RUN pixi install --locked -e docker

FROM gcr.io/distroless/base-debian13:latest@sha256:9ef50bca108839d5986e4d84b7f7b2d79024c9293b7c35b162c6c55485bd5868 AS production
ENV PATH="/app/.pixi/envs/docker/bin:$PATH"
EXPOSE 8080
WORKDIR /app
COPY --from=build /app/.pixi/envs/docker /app/.pixi/envs/docker
COPY src/ ./
COPY THIRD_PARTY_NOTICES.md LICENSE ./
HEALTHCHECK CMD ["curl", "--fail", "http://localhost:8080/_stcore/health"]
ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8080", "--server.address=0.0.0.0"]
