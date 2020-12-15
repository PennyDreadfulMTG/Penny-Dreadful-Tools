FROM nikolaik/python-nodejs:python3.8-nodejs12 AS python

WORKDIR /restore
RUN pip install pipenv
COPY Pipfile Pipfile.lock ./
RUN pipenv lock -r > requirements.txt
RUN pip install -r requirements.txt
CMD ["/bin/bash"]

FROM nikolaik/python-nodejs:python3.8-nodejs12 AS js

WORKDIR /restore
COPY package*.json ./
RUN npm ci --verbose

FROM nikolaik/python-nodejs:python3.8-nodejs12

COPY --from=python /usr/local/lib/python3.8/site-packages/ /usr/local/lib/python3.8/site-packages/
COPY --from=js /restore/node_modules /pdm/node_modules

WORKDIR /pdm

COPY dev.py run.py analysis/ decksite/ logsite/ magic/ maintenance/ shared*/ card_aliases.tsv ./
COPY ./.git/ ./

CMD [ "python3", "run.py", "--wait-for-db", "decksite" ]
