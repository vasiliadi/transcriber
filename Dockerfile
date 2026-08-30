FROM ghcr.io/prefix-dev/pixi:trixie@sha256:7048c87239bf8c7872feeacd0c25c9f3788fd3cd89950579b7233143265b8774 AS build
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
