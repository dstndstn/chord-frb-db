import sys

import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'

# mysql --host=10.5.2.30 --user=chimefrb --password=chimefrb commissioning

# [dstn@frb-analysis ~]$ docker run --net=host --mount type=bind,source=$(pwd),target=/pwd -w /pwd dstndstn/mysql python3 /pwd/db-test.py

import MySQLdb

db = MySQLdb.connect(host='10.5.2.30', user='chimefrb', password='chimefrb', database='commissioning')
print(db)

'''
MariaDB [commissioning]> describe event_register;
+------------------+----------------------+------+-----+---------+----------------+
| Field            | Type                 | Null | Key | Default | Extra          |
+------------------+----------------------+------+-----+---------+----------------+
| rfi_grade_level2 | double               | NO   |     | NULL    |                |
| timestamp_utc    | datetime(6)          | YES  |     | NULL    |                |
| event_no         | int(11)              | NO   | PRI | NULL    | auto_increment |
| is_rfi           | tinyint(1)           | NO   |     | NULL    |                |
| is_delayed       | tinyint(1)           | NO   |     | NULL    |                |
| is_test          | tinyint(1)           | NO   |     | NULL    |                |
| beam_activity    | smallint(5) unsigned | YES  |     | NULL    |                |
+------------------+----------------------+------+-----+---------+----------------+
'''

cursor = db.cursor()

print('Cursor array size:', cursor.arraysize)
#sys.exit(0)

#c.execute("SELECT COUNT(*) FROM event_register")
#  318,173,770

#c.execute("SELECT MAX(event_no) FROM event_register")
#  375_913_078

'''
(318000001, datetime.datetime(2023, 9, 11, 23, 52, 38, 164521), 0.0012149889921711158, 1, 0, 0, 944)
<class 'int'> 318000001
<class 'datetime.datetime'> 2023-09-11 23:52:38.164521
<class 'float'> 0.0012149889921711158
<class 'int'> 1
<class 'int'> 0
<class 'int'> 0
<class 'int'> 944
'''

import fitsio
import numpy as np

if False:
    cursor.execute('''SELECT event_no,timestamp_utc,rfi_grade_level2,is_rfi,is_delayed,is_test,beam_activity
                 FROM event_register
                 WHERE event_no > %s''', (365_000_000,))
    #       LIMIT 100
    
    print('Results:')
    results = cursor.fetchall()
    print(len(results))
    
    N = len(results)
    E = np.zeros(N, np.int32)
    T = np.zeros(N, np.float64)
    #TS = np.zeros((N,26), np.byte)
    TS = []
    R = np.zeros(N, np.float32)
    isR = np.zeros(N, bool)
    isD = np.zeros(N, bool)
    isT = np.zeros(N, bool)
    A = np.zeros(N, np.int32)
    
    inext = 2
    for i,(e,t,r,isrfi,isdel,istest,ba) in enumerate(results):
        tx = t.timestamp()
        if i >= inext:
            print('Row', i, 'Timestamp:', t)
            inext *= 2
        ts = str(t).encode()
        TS.append(ts)
        E[i] = e
        T[i] = tx
        R[i] = r
        isR[i] = isrfi
        isD[i] = isdel
        isT[i] = istest
        A[i] = ba
    TS = np.array(TS)
    
    fitsio.write('db-event-register.fits', dict(event_no=E, timestamp_utc=T, timestamp_utc_str=TS,
                                 rfi_grade_level2=R, is_rfi=isR,
                                 is_delayed=isD, is_test=isT, beam_activity=A),
                 clobber=True)

from anfits import fits_table
#tab = fitsio.read('db-event-register.fits')
#print(type(tab), len(tab))
#print(dir(tab))
#print(tab.fields)
#T = fits_table('db-event-register.fits')
T = fits_table('db-event-register.fits', columns=['event_no'])
print(len(T))
T.about()
elo,ehi = T.event_no.min(), T.event_no.max()

if True:
    # MariaDB [commissioning]> describe event_best_data
    cols = ('combined_snr pos_ra_deg pos_dec_deg dm dm_error spectral_index spectral_index_error ' +
            'timestamp_utc pos_error_semimajor_deg_68 pos_error_semiminor_deg_68 pos_error_theta_deg_68 ' +
            'flux_mjy source_category_name source_category_type dm_gal_ne_2001_max dm_gal_ymw_2016_max ' +
            'pulse_width_ms')
    cols = cols.split()
    print('Columns', cols)
    
    sql = 'SELECT ' + ','.join(cols) + ' FROM event_best_data WHERE event_no between %s and %s' #+ ' limit 100'
    print('SQL:', sql)
    cursor.execute(sql, (elo,ehi))
    print('Results:')
    R = fits_table()
    for c in cols:
        R.set(c, [])
    arrs = [R.get(c) for c in cols]
    is_date = [c in ['timestamp_utc'] for c in cols]
    inext = 2
    print('Cursor array size:', cursor.arraysize)
    i = 0
    while True:
        results = cursor.fetchmany(1000)
        print('Got', len(results), 'more results')
        if len(results) == 0:
            break
    
        for r in results:
            i += 1
            if i >= inext:
                print('Row', i)
                inext *= 2
            for a,rr,isdate in zip(arrs, r, is_date):
                if isdate:
                    rr = rr.timestamp()
                a.append(rr)
    R.to_np_arrays()
    R.writeto('db-event-best.fits')

if False:
    cols = ('snr snr_scale pos_ra_deg  pos_ra_error_deg pos_dec_deg  pos_dec_error_deg dm    dm_error   spectral_index scattering_measure rfi_grade_level1 level1_nhits  tree_index  rfi_mask_fraction ' +
            'rfi_clip_fraction timestamp_fpga timestamp_utc  beam_no   event_no   is_incoherent  time_error')
    cols = cols.split()
    print('Columns', cols)
    
    sql = 'SELECT ' + ','.join(cols) + ' FROM event_beam_header WHERE event_no between %s and %s'
    #sql += ' LIMIT 10'
    print('SQL:', sql)
    cursor.execute(sql, (elo,ehi))
    
    print('Results:')
    #results = c.fetchall()
    #print(len(results))
    #print('Columns:', cols)
    #print(results)
    
    R = fits_table()
    for c in cols:
        R.set(c, [])
    arrs = [R.get(c) for c in cols]
    is_date = [c in ['timestamp_utc'] for c in cols]
    inext = 2
    
    print('Cursor array size:', cursor.arraysize)
    
    i = 0
    while True:
        results = cursor.fetchmany(1000)
        print('Got', len(results), 'more results')
        if len(results) == 0:
            break
    
        for r in results:
            i += 1
            if i >= inext:
                print('Row', i)
                inext *= 2
            for a,rr,isdate in zip(arrs, r, is_date):
                if isdate:
                    rr = rr.timestamp()
                a.append(rr)
    R.to_np_arrays()
    R.writeto('db-event-header.fits')
