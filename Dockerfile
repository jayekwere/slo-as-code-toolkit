FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS builder
WORKDIR /app
RUN python -m pip install --no-cache-dir uv==0.13.6
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY sloctl ./sloctl
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
RUN useradd --create-home --uid 10001 sloctl
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1
WORKDIR /home/sloctl
USER 10001:10001
ENTRYPOINT ["sloctl"]
CMD ["--help"]
