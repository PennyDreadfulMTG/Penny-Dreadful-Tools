FROM nikolaik/python-nodejs:python3.12-nodejs22 AS python

WORKDIR /pdm
RUN pip install pipenv
COPY Pipfile Pipfile.lock ./
RUN pipenv sync
CMD ["/bin/bash"]

FROM nikolaik/python-nodejs:python3.12-nodejs22 AS js

WORKDIR /restore
COPY package*.json ./
RUN npm ci --verbose

FROM nikolaik/python-nodejs:python3.12-nodejs22

COPY --from=python /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=python /root/.local/share/virtualenvs/ /root/.local/share/virtualenvs/
COPY --from=js /restore/node_modules /pdm/node_modules

WORKDIR /pdm

COPY Pipfile Pipfile.lock ./
RUN pipenv sync

COPY dev.py run.py analysis/ decksite/ find/ logsite/ magic/ maintenance/ shared*/ card_aliases.tsv hq_artcrops.json ./
COPY ./.git/ ./

CMD [ "pipenv", "run", "python", "run.py", "--wait-for-db", "decksite" ]
