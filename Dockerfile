FROM nikolaik/python-nodejs:python3.10-nodejs16 AS python

WORKDIR /pdm
RUN pip install pipenv
COPY Pipfile* ./
ENV PIPENV_VENV_IN_PROJECT=1
RUN pipenv install
CMD ["/bin/bash"]

FROM nikolaik/python-nodejs:python3.10-nodejs16 AS js

WORKDIR /restore
COPY package*.json ./
RUN npm ci --verbose

FROM nikolaik/python-nodejs:python3.10-nodejs16
RUN pip install pipenv

COPY --from=python /pdm/.venv/ /pdm/.venv/
COPY --from=js /restore/node_modules /pdm/node_modules

WORKDIR /pdm

COPY Pipfile* ./
RUN pipenv install

COPY dev.py run.py analysis/ decksite/ find/ logsite/ magic/ maintenance/ shared*/ card_aliases.tsv ./
COPY ./.git/ ./

RUN pipenv install
CMD [ "pipenv", "run", "python", "run.py", "--wait-for-db", "decksite" ]
