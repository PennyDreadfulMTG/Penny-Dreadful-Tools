FROM python:3.10-bookworm AS python-build
RUN pip install pipenv

WORKDIR /pdm
COPY Pipfile Pipfile.lock ./
RUN pipenv sync


FROM node:22-bookworm AS js-build

WORKDIR /restore
COPY package*.json ./
RUN npm ci --verbose


FROM python:3.10-bookworm
RUN pip install pipenv

COPY --from=python-build /usr/local/lib/python3.10/site-packages/ /usr/local/lib/python3.10/site-packages/
COPY --from=python-build /root/.local/share/virtualenvs/ /root/.local/share/virtualenvs/
COPY --from=js-build /restore/node_modules /pdm/node_modules

WORKDIR /pdm

COPY Pipfile Pipfile.lock ./
RUN pipenv sync

COPY dev.py run.py analysis/ decksite/ find/ logsite*/ magic/ maintenance/ shared*/ card_aliases.tsv hq_artcrops.json ./
COPY ./.git/ ./

ENTRYPOINT ["pipenv", "run", "python", "run.py", "--wait-for-db"]
