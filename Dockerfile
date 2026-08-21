FROM python:3.13-bookworm
ARG UV_VERSION=0.9.26
RUN pip install "uv==$UV_VERSION"

WORKDIR /pdm

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --dev

COPY dev.py run.py analysis/ decksite/ find/ logsite*/ magic/ maintenance/ shared*/ card_aliases.tsv hq_artcrops.json ./
COPY ./.git/ ./

ENTRYPOINT ["uv", "run", "--frozen", "python", "run.py", "--wait-for-db"]
