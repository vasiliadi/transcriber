FROM ghcr.io/prefix-dev/pixi:trixie@sha256:fb74bc8abf05e6c3ec41d59ec4c28b4c92c1faa54ca628cfd65400477860ab23 AS build
WORKDIR /app
COPY pyproject.toml pixi.lock ./
RUN pixi install --locked -e docker

FROM gcr.io/distroless/base-debian13:latest@sha256:7c4468db5fea18a1630860619be640c4c0ad158c0d63f12951b96b7d0f5ddd62 AS production
ENV PATH="/app/.pixi/envs/docker/bin:$PATH"
EXPOSE 8080
WORKDIR /app
COPY --from=build /app/.pixi/envs/docker /app/.pixi/envs/docker
COPY src/ ./
COPY THIRD_PARTY_NOTICES.md LICENSE ./
HEALTHCHECK CMD ["curl", "--fail", "http://localhost:8080/_stcore/health"]
ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8080", "--server.address=0.0.0.0"]
