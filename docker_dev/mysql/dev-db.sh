if [ "$PDM_DOWNLOAD_DEVDB" = "true" ]
then
    curl https://pennydreadfulmagic.com/static/dev-db.sql.gz >dev-db.sql.gz
    gunzip dev-db.sql.gz
    mysql -u pennydreadful decksite <dev-db.sql
else
    echo 'PDM_DOWNLOAD_DEVDB!=true.  Not downloading devdb'
fi
