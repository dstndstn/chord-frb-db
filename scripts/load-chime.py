import os
import sys

import pylab as plt
import numpy as np

from astrometry.util.fits import fits_table

from sqlalchemy import create_engine, insert, update, select, func, cast, Numeric
from sqlalchemy.orm import Session, load_only

from chord_frb_db.models import Event, EventBeam, KnownSource

def get_db_engine():
    db_url = 'postgresql+psycopg2://chordfrb:PASSWORD@localhost:5432/chordfrb'
    db_pass = os.environ.get('CHORD_FRB_DB_PASSWORD')
    if db_pass is not None:
        db_url = db_url.replace('PASSWORD', db_pass)
    engine = create_engine(db_url)
    # Print each SQL statement?
    #echo=True)
    return engine

def update_event_best():
    T = fits_table('../db-event-best.fits')
    print(len(T), 'event-best')
    T.about()

    engine = get_db_engine()
    with Session(engine) as session:

        batchsize = 10000
        nbatches = (len(T) + batchsize-1) // batchsize

        T.rename('combined_snr', 'total_snr')
        T.rename('pos_ra_deg', 'ra')
        T.rename('pos_dec_deg', 'dec')
        # The thetas are ~ always 0.
        T.rename('pos_error_semimajor_deg_68', 'ra_error')
        T.rename('pos_error_semiminor_deg_68', 'dec_error')
        T.rename('flux_mjy', 'flux')
        # To Janskies
        T.flux *= 0.001
        T.rename('pulse_width_ms', 'pulse_width')
        T.rename('dm_gal_ne_2001_max', 'dm_ne2001')
        T.rename('dm_gal_ymw_2016_max', 'dm_ymw2016')

        from collections import Counter

        #for n,k in Counter(list(zip(T.source_category_type, T.source_category_name))).most_common():
        #print(n, k)

        r = session.execute(select(func.count(KnownSource.id)))
        print('Number of known sources:', r.all())
    
        keys = ('total_snr ra dec dm dm_error spectral_index ra_error dec_error flux ' +
                'dm_ne2001 dm_ymw2016 pulse_width')
        keys = keys.split()
        arrs = [T.get(k) for k in keys]
        types = [float]*len(keys)

        known_cache = {}
        
        print('Updating', nbatches, 'batches of', batchsize, 'events')
        for i in range(nbatches):
            vals = []
            for j in range(i*batchsize, min(len(T), (i+1)*batchsize)):
                d = dict([(k, t(a[j])) for k,a,t in zip(keys, arrs, types)])
                d.update(event_id=int(T.event_no[j]))

                known_name = None

                typ = T.source_category_type[j]
                name = T.source_category_name[j]
                if typ == 'RFI':
                    d.update(is_rfi=True)
                elif typ == 'KNOWN':
                    if name.startswith('J') or name.startswith('B'):
                        d.update(is_known_pulsar=True)
                    else:
                        # ???
                        #print('Known / non-pulsar:', name)
                        d.update(is_new_burst=True)
                        if name.startswith('FRB'):
                            d.update(is_repeating_frb=True)
                        # else:
                        #    -- these are integers, our own event_nos of previous bursts.
                    known_name = name
                elif typ == 'UNKNOWN':
                    d.update(is_new_burst=True)
                    if name == 'EXT':
                        d.update(is_frb=True)

                #
                if known_name is not None:
                    if known_name in known_cache:
                        d.update(known_id = known_cache[known_name])
                    else:
                        # Look it up / add it!
                        stmt = select(KnownSource.id).where(KnownSource.name == known_name)
                        res = session.execute(stmt)
                        #print('Known source lookup result:', res)
                        r = res.first()
                        #print('r', r)
                        if r is not None:
                            ksid = r[0]
                        else:
                            kvals = dict(name=known_name)
                            ks = session.execute(insert(KnownSource).returning(KnownSource.id), kvals)
                            #print('KS', ks)
                            ks = ks.first()
                            #print('KS', ks)
                            ksid = ks[0]
                            print('Added known source', known_name, '->', ksid)
                        known_cache[known_name] = ksid
                        d.update(known_id = ksid)

                vals.append(d)

            session.execute(update(Event), vals)
            print('.', end='')
            sys.stdout.flush()
        print()
        print('Committing')
        session.commit()

def insert_event_register():
    T = fits_table('../db-event-register.fits')
    print(len(T), 'event-register')
    T.about()

    engine = get_db_engine()
    with Session(engine) as session:

        batchsize = 10000
        nbatches = (len(T) + batchsize-1) // batchsize

        keys = ['event_id', 'timestamp', 'rfi_grade', 'is_rfi', 'beam_activity']
        arrs = [T.event_no, T.timestamp_utc, T.rfi_grade_level2, T.is_rfi,
                T.beam_activity]
        types = [int, float, float, bool, int]

        print('Inserting', nbatches, 'batches of', batchsize, 'events')
        for i in range(nbatches):
            vals = []
            for j in range(i*batchsize, min(len(T), (i+1)*batchsize)):
                vals.append(dict([(k, t(a[j])) for k,a,t in zip(keys, arrs, types)]))

            session.execute(insert(Event), vals)
            print('.', end='')
            sys.stdout.flush()
        print()
        print('Committing')
        session.commit()

def plot_rfi_grade():
    tt = []
    rfi_grade = []
    is_rfi = []

    engine = get_db_engine()

    with Session(engine) as session:
        cellcount = func.count(Event.event_id)
        rt = func.round(2.0 * cast(Event.timestamp, Numeric), -5) / 2.0
        #rr = func.round(cast(Event.rfi_grade, Numeric), 1)
        rr = func.round(cast(Event.rfi_grade, Numeric) / 2.0, 1) * 2.0
        #stmt = select(Event).options(load_only(Event.timestamp, Event.rfi_grade, Event.is_rfi))
        stmt = select(cellcount, rt, rr)
        # Some small fraction have timestamp ~ 1970...
        stmt = stmt.where(Event.timestamp > 1e9)
        stmt = stmt.group_by(rt, rr)
        print('Statement:', stmt)

        events = session.execute(stmt)
        print('events:', events)

        counts = []
        times = []
        rfis = []

        for res in events.partitions(10_000):
            print('res', type(res), len(res), res[0])
            counts.extend([r[0] for r in res])
            times .extend([r[1] for r in res])
            rfis  .extend([r[2] for r in res])

    print('Max counts:', max(counts))

    plt.scatter(times, rfis, s=np.sqrt(counts)/50)
    plt.savefig('rfi2.png')

    return
        
    with Session(engine) as session:

        # This returns results as (partially-filled) Event objects
        #stmt = select(Event).options(load_only(Event.timestamp, Event.rfi_grade, Event.is_rfi))

        stmt = select(Event.timestamp, Event.rfi_grade, Event.is_rfi) #.options(load_only(Event.timestamp, Event.rfi_grade, Event.is_rfi))
        # Some small fraction have timestamp ~ 1970...
        stmt = stmt.where(Event.timestamp > 1e9)
        batch = 100_000
        stmt = stmt.execution_options(yield_per=batch)

        #events = session.scalars(stmt).all()
        #print(events[:10])

        print('Statement:', stmt)
        # events: sqlalchemy.engine.result.ChunkedIteratorResult
        events = session.execute(stmt)
        print('events:', events)

        for res in events.partitions(): #10_000):
            #print('res', type(res), len(res), res[0])
            print('.', end='')
            sys.stdout.flush()

            tt       .extend([r[0] for r in res])
            rfi_grade.extend([r[1] for r in res])
            is_rfi   .extend([r[2] for r in res])
        #for res in events.fetchmany(batch):
        #      print('res', type(res), len(res), res[0])
        #     return

        # # events: sqlalchemy.engine.result.ScalarResult
        # events = session.scalars(stmt)
        # print('events:', events)
        # for res in events.partitions(): #10_000):
        #     # If you access a field not listed in the load_only(), it will transparently fetch it
        #     # from the database!
        #     #print('10k', type(res), res[0], res[0].beam_activity)
        # 
        #     # If you select(Event):
        #     # res <class 'list'> 100000 <chord_frb_db.models.Event object at 0x77357f4c1e70>
        # 
        #     # res <class 'list'> 100000 1712042029.864727
        #     print('res', type(res), len(res), res[:10])
        #     print('.', end='')
        #     sys.stdout.flush()
        # 
        #     tt       .extend([r.timestamp for r in res])
        #     rfi_grade.extend([r.rfi_grade for r in res])
        #     is_rfi   .extend([r.is_rfi    for r in res])
        print()
        print(len(tt))
        #ae = events.all()
        #print('all:', ae)

    plt.scatter(tt, rfi_grade, c=is_rfi, s=4)
    plt.savefig('rfi.png')
    
#insert_event_register()
update_event_best()
#plot_rfi_grade()            
