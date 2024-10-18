Prototyping a database & Python interface for the CHORD/Fast Radio Burst project

# Notes about Sqlalchemy & Alembic Setup

Ubuntu 24.04 packages are older than we want (v2.0+) -- use `pip` to install new versions:

```
sudo pip install sqlalchemy --break-system-packages
sudo pip install alembic --break-system-packages
sudo pip install flask_sqlalchemy --break-system-packages
```

Along with
```
sudo apt install postgresql-common libpq-dev
sudo pip install psycopg2 --break-system-packages
```

The database URL is specified in the file `chord_frb_db/alembic.ini` as the `sqlalchemy.url` variable.

If you set the environment variable `CHORD_FRB_DB_PASSWORD`, that will get plugged into
the default database URL.

If you set the environment variable `CHORD_FRB_DB_URL`, that database URL will get used instead.  For example, for local `sqlite3` testing,

```
export CHORD_FRB_DB_URL=sqlite+pysqlite:///db.sqlite3
```


# Notes about alembic in normal use

```
cd chord_frb_db && alembic revision --autogenerate -m "add initial models"
cd chord_frb_db && alembic upgrade head
```

You should then `git add` the `chord_frb_db/alembic/version/*.py` files.


# Notes about flask

Good tutorial

https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-i-hello-world

flask --app web.webapp run --reload
 (--debug)