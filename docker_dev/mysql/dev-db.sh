if [ "$PDM_DOWNLOAD_DEVDB" = "true" ]
then
    curl https://pennydreadfulmagic.com/static/dev-db.sql.gz -o dev-db.sql.gz
    gunzip dev-db.sql.gz
    echo USE decksite > /docker-entrypoint-initdb.d/dev-db.sql
    cat dev-db.sql >> /docker-entrypoint-initdb.d/dev-db.sql
    rm dev-db.sql
else
    echo 'PDM_DOWNLOAD_DEVDB!=true.  Not downloading devdb'
fi
