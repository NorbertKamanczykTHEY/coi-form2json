# Kreuzberg ships only manylinux (glibc) wheels, no musllinux: Alpine would mean building its Rust core + Tesseract + PDFium from source.
FROM ghcr.io/astral-sh/uv:0.11.9 AS uv

FROM python:3.14.10-slim-trixie AS build
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.14.10-slim-trixie
# Tesseract CLI + Polish model (Apache-2.0; Kreuzberg's Linux wheel has no Tesseract backend); DejaVu font for the spreadsheet render
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-pol fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --system --uid 10001 --no-create-home coi && install -d -o coi /data
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY coi ./coi
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1
USER coi
EXPOSE 8000
# a scan page can climb the whole VLM ladder: long timeout, threads so one slow request does not block the worker;
# --preload: create_app() (create_all + dictionary seed) runs once in the master, not racing in every worker
CMD ["gunicorn", "--preload", "--no-control-socket", "--bind", "0.0.0.0:8000", "--workers", "2", "--worker-class", "gthread", "--threads", "4", "--timeout", "600", "coi:create_app()"]
