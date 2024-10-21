from flask import Flask, request
from .config import Config
from flask import render_template
import sys

from flask_sqlalchemy import SQLAlchemy

from chord_frb_db.models import Event, EventBeam

import sqlalchemy as sa

#from flask import session
#print('Config:', Config)

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)

@app.route('/l1-events/<int:event_id>')
def l1_event_list(event_id):
    query = sa.select(EventBeam).filter_by(event_id=event_id)
    r = db.session.execute(query).scalars()
    print('r:', r)

    query = sa.select(Event).filter_by(event_id=event_id)
    event = db.session.execute(query).scalar_one()
    print('event:', event)

    fields = ['beam', 'snr', 'timestamp_utc', 'timestamp_fpga']
    return render_template('l1_event_list.html', event_id=event_id,
                           event=event, l1_events=r, fields=fields)

@app.route("/")
def event_list(): #(name=None):
    query = sa.select(Event).order_by(Event.event_id)#.desc())
    #order_by(Event.timestamp.desc())
    print('Query:', query)
    #print(dir(query))

    # #print('Count:', query.count())
    # #count_query = query.statement.with_only_columns([sa.func.count()]).order_by(None)
    # #count = q.session.execute(count_query).scalar()
    # count = sa.select(sa.func.count(Event.event_id))#.scalar()
    # print('Count:', type(count), count)
    # r = db.session.execute(count).scalar()
    # print(type(r), r)
    # n_events = r

    page = request.args.get("page")
    #print('page:', page)
    try:
        page = int(page)
    except:
        page = 1
    
    event_pager = db.paginate(query, page=page, per_page=20, error_out=False)
    events = event_pager.items
    
    fields = [ 'event_id', 'timestamp', 'rfi_grade', 'total_snr', 'dm', 'ra', 'dec', 'nbeams', 'dm_ne2001', 'dm_ymw2016', 'flux', 'fluence', 'pulse_width' ]

    return render_template('event_list.html', event_pager=event_pager, events=events, fields=fields)



#if __name__ == '__main__':
    
