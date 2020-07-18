FROM mariadb

RUN apt-get update; apt-get install -y curl
COPY ./*.sql ./*.sh /docker-entrypoint-initdb.d/

EXPOSE 3306

CMD ["mysqld"]
