import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get('CHORD_FRB_DB_URL')
    TEMPLATES_AUTO_RELOAD = True
