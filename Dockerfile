FROM ghcr.io/prefix-dev/pixi:trixie@sha256:f743d986378ae555998a526cae9a6c39d1174ce1f8f572b0008bed4fd6b8d8ae AS build
WORKDIR /app
COPY pyproject.toml pixi.lock ./
RUN pixi install --locked -e docker

FROM gcr.io/distroless/base-debian13:latest@sha256:f4a335ca209e1d2ee873102c17c389ad0142e3d5b21aee2817e9cc9c01d87d20 AS production
ENV PATH="/app/.pixi/envs/docker/bin:$PATH"
EXPOSE 8080
WORKDIR /app
COPY --from=build /app/.pixi/envs/docker /app/.pixi/envs/docker
COPY src/ ./
COPY THIRD_PARTY_NOTICES.md LICENSE ./
HEALTHCHECK CMD ["curl", "--fail", "http://localhost:8080/_stcore/health"]
ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8080", "--server.address=0.0.0.0"]
