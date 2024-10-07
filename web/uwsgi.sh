#! /bin/bash

cd /home/dstn/chord/chord-frb-db

# get CHORD_FRB_DB_PASSWORD, CHORD_FRB_DB_URL, PYTHONPATH
source /home/dstn/.bashrc

uwsgi --plugin python3 --socket :3000 --wsgi-file=web/wsgi.py --touch-reload=web/wsgi.py --processes 8 --reload-on-rss 768 -d uwsgi.log
