#!/bin/bash
mysql -u pennydreadful -e "CREATE USER 'pennydreadful'@'%' IDENTIFIED BY '$mysql_passwd';"
