from flask import Flask, request, make_response
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

@app.route('/')
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



@app.route('/events.png')
def event_plot():
    from datetime import datetime

    query = sa.select(Event).order_by(Event.event_id.desc()).limit(1000)
    print('Query:', query)
    r = db.session.execute(query)#.scalar()
    print('Result:', r)

    xx = []
    yy = []
    cc = []

    for e in r:
        (e,) = e
        #print('  event:', e)
        d = datetime.fromtimestamp(e.timestamp)
        print('timestamp:', e.timestamp, '-> date', d)
        xx.append(d)
        #xx.append(e.timestamp)
        #xx.append(e.event_id)
        yy.append(e.dm)
        cc.append(e.rfi_grade)


    from io import BytesIO
    from matplotlib.figure import Figure
    from mpl_toolkits.axes_grid1 import make_axes_locatable
    
    fig = Figure()
    ax = fig.subplots()
    scat = ax.scatter(xx, yy, c=cc, s=4, vmin=0, vmax=10, cmap='inferno')#copper')
    ax.set_yscale('log')
    ax.set_xlabel('Date')
    ax.set_ylabel('DM')
    ax.set_facecolor('0.6')
    #divider = make_axes_locatable(0)
    #cax = divider.append_axes('right', size='5%', pad=0.05)
    #fig.colorbar(scat, cax=cax, orientation='vertical')
    cb = fig.colorbar(scat, cax=None, ax=ax)
    cb.set_label('RFI grade')
    buf = BytesIO()
    fig.savefig(buf, format="png")
    #buf = buf.getbuffer()
    buf = buf.getvalue()

    resp = make_response(buf)
    resp.headers['Content-type'] = 'image/png'
    return resp

#if __name__ == '__main__':
    
