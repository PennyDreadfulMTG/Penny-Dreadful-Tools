if [ "$PDM_DOWNLOAD_DEVDB" = "true" ]
then
    curl https://pennydreadfulmagic.com/static/dev-db.sql.gz | gunzip | mysql -u pennydreadful decksite
else
    echo 'PDM_DOWNLOAD_DEVDB!=true.  Not downloading devdb'
fi
