from flask import Flask, request
from .config import Config
from flask import render_template
import sys

from flask_sqlalchemy import SQLAlchemy

from chord_frb_db.models import Event

import sqlalchemy as sa

#from flask import session

print('Config:', Config)

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)

@app.route("/")
#def hello_world():
#    return "<p>Hello, World!</p>"
def hello(): #(name=None):
    query = sa.select(Event).order_by(Event.event_id)#.desc())
    #order_by(Event.timestamp.desc())
    print('Query:', query)
    print(dir(query))

    # #print('Count:', query.count())
    # #count_query = query.statement.with_only_columns([sa.func.count()]).order_by(None)
    # #count = q.session.execute(count_query).scalar()
    # count = sa.select(sa.func.count(Event.event_id))#.scalar()
    # print('Count:', type(count), count)
    # r = db.session.execute(count).scalar()
    # print(type(r), r)
    # n_events = r

    page = request.args.get("page")
    print('page:', page)
    try:
        page = int(page)
    except:
        page = 1
    
    event_pager = db.paginate(query, page=page, per_page=20, error_out=False)
    events = event_pager.items
    
    #print('Events is', type(events), events)

    fields = [ 'event_id', 'timestamp', 'rfi_grade', 'total_snr', 'dm', 'ra', 'dec', 'nbeams', 'dm_ne2001', 'dm_ymw2016', 'flux', 'fluence', 'pulse_width' ]

    return render_template('hello.html', event_pager=event_pager, events=events, fields=fields)



#if __name__ == '__main__':
    
