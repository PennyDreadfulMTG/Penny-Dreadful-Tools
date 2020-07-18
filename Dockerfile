FROM nikolaik/python-nodejs:latest AS python

WORKDIR /restore
COPY requirements.txt ./
RUN pip install -r requirements.txt
CMD ["/bin/bash"]

FROM nikolaik/python-nodejs:latest AS js

WORKDIR /restore
COPY package*.json ./
RUN npm ci --verbose

FROM nikolaik/python-nodejs:latest

COPY --from=python /usr/local/lib/python3.8/site-packages/ /usr/local/lib/python3.8/site-packages/
COPY --from=js /restore/node_modules /pdm/node_modules

WORKDIR /pdm

COPY dev.py run.py analysis decksite logsite magic maintenance shared* card_aliases.tsv ./
COPY ./.git/ ./

CMD [ "python3", "run.py", "--wait-for-db", "decksite" ]
