# Personal Brain V1 server image (reproducible, non-root)
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10001 brain \
    && mkdir -p /srv/brain/data && chown -R brain:brain /srv/brain

WORKDIR /srv/brain

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir 'uv>=0.12.6,<0.13' \
    && uv sync --locked --no-dev --no-install-project

COPY apps ./apps
COPY packages ./packages
COPY migrations ./migrations
COPY alembic.ini ./

RUN uv sync --locked --no-dev --offline \
    && pip uninstall -y uv

ENV PATH="/srv/brain/.venv/bin:$PATH"

USER brain
EXPOSE 18081

CMD ["python", "-m", "personal_brain_server"]
