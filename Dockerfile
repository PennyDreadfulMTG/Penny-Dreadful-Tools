FROM python:3.10-bookworm
RUN pip install pipenv

WORKDIR /pdm

COPY Pipfile Pipfile.lock ./
RUN pipenv sync --dev

COPY dev.py run.py analysis/ decksite/ find/ logsite*/ magic/ maintenance/ shared*/ card_aliases.tsv hq_artcrops.json ./
COPY ./.git/ ./

ENTRYPOINT ["pipenv", "run", "python", "run.py", "--wait-for-db"]
