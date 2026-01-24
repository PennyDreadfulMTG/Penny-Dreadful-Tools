FROM python:3.13-bookworm
RUN pip install uv

WORKDIR /pdm

COPY pyproject.toml ./
RUN uv sync --dev

COPY dev.py run.py analysis/ decksite/ find/ logsite*/ magic/ maintenance/ shared*/ card_aliases.tsv hq_artcrops.json ./
COPY ./.git/ ./

ENTRYPOINT ["uv", "run", "python", "run.py", "--wait-for-db"]
