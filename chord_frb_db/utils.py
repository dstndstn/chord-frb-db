def get_db_engine():
    import os
    from sqlalchemy import create_engine, text
    from chord_frb_db.models import Base
    db_url = os.environ.get('CHORD_FRB_DB_URL', 'sqlite+pysqlite:///db.sqlite3')
    #print('Using database URL:', db_url)
    #engine = create_engine(db_url, echo=True)
    engine = create_engine(db_url, echo=False)
    if 'sqlite' in db_url:
        with engine.connect() as conn:
            conn.execute(text('PRAGMA journal_mode=WAL'))
            conn.execute(text('PRAGMA synchronous=NORMAL'))
        # Make sure database tables exist
        Base.metadata.create_all(engine)
    engine.is_sqlite = 'sqlite' in db_url
    return engine
