from flask import Flask
from .config import Config
from flask import render_template
import sys

from flask_sqlalchemy import SQLAlchemy

from chord_frb_db.models import Event

import sqlalchemy as sa

#from flask import session

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)

@app.route("/")
#def hello_world():
#    return "<p>Hello, World!</p>"
def hello(): #(name=None):
    name = None

    query = sa.select(Event).order_by(Event.timestamp.desc())
    events = db.paginate(query, page=1, per_page=20, error_out=False).items

    #print('Events is', type(events), events)

    fields = [ 'id', 'timestamp_fpga', 'rfi_grade', 'total_snr', 'dm', 'ra', 'dec', 'nbeams', 'dm_ne2001', 'dm_ymw2016', 'flux', 'fluence', 'pulse_width' ]

    return render_template('hello.html', events=events, fields=fields) #person=name)
