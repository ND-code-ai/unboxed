# The API as the Nebius endpoint runs it (docs/building_the_project.md, "Deployment"). Built by
# .github/workflows/deploy.yml for linux/amd64. No setting and no secret is in the image: the
# endpoint passes them in. tests/fixtures is here for SHOPPER_SOURCES=fixtures, the rehearsal's.
FROM ghcr.io/astral-sh/uv:0.12.22-python3.12-trixie-slim

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY tests/fixtures ./tests/fixtures
RUN uv sync --frozen --no-dev

EXPOSE 8080
CMD [".venv/bin/uvicorn", "shopper.api.main:app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log"]
