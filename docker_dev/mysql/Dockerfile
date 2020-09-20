FROM mariadb

RUN apt-get update; apt-get install -y curl dos2unix
COPY ./*.sql ./*.sh /docker-entrypoint-initdb.d/
RUN dos2unix /docker-entrypoint-initdb.d/* && apt-get --purge remove -y dos2unix && rm -rf /var/lib/apt/lists/*
EXPOSE 3306

CMD ["mysqld"]
