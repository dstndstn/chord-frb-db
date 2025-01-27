'''
ATNF Pulsar Catalog - 3748 pulsars

wget "https://www.atnf.csiro.au/research/pulsar/psrcat/proc_form.php?version=2.5.1&Name=Name&JName=JName&RAJD=RAJD&DecJD=DecJD&DM=DM&S400=S400&S1400=S1400&startUserDefined=true&sort_attr=jname&sort_order=asc&condition=&coords_unit=raj%2Fdecj&radius=&coords_1=&coords_2=&pulsar_names=&ephemeris=short&style=long+csv+with+errors&no_value=*&fsize=3&table_submit=&x_axis=&x_scale=linear&y_axis=&y_scale=linear&state=query" -O psrcat.html

This has an HTML wrapper, with the CSV contents in a <pre>...</pre> block.
'''

from chord_frb_db.models import KnownSource
from chord_frb_db.utils import get_db_engine
from sqlalchemy.orm import Session
from sqlalchemy import delete

def main():
    lines = open('psrcat.html').readlines()
    i0 = lines.index('<pre>\n')
    i1 = lines.index('</pre>\n')
    lines = lines[i0+1 : i1]
    print('Got', len(lines), 'pulsars')
    # 2 lines of headers
    assert(len(lines) == 3748 + 2)
    lines = lines[2:]
    #  #;NAME;;PSRJ;;RAJD;;DECJD;;DM;;;S400;;;S1400;;;
    #  ;;;;;(deg);;(deg);;(cm^-3pc);;;(mJy);;;(mJy);;;
    #  1;J0002+6216;cwp+17;J0002+6216;cwp+17;0.74238;8.3e-05;62.26928;2.8e-05;218.6;6.0e-01;wcp+18;*;0;*;0.022;0;wu18;

    engine = get_db_engine()

    # Drop all existing data!!!

    print('Dropping existing known sources!!')
    with Session(engine) as session:
        st = delete(KnownSource)
        session.execute(st)
        session.commit()

    with Session(engine) as session:
        for line in lines:
            words = line.split(';')
            assert(len(words) == 19)

            name = words[1]
            ra = words[5]
            d_ra = words[6]
            dec = words[7]
            d_dec = words[8]
            dm = words[9]
            d_dm = words[10]
            s400 = words[12]
            d_s400 = words[13]
            s1400 = words[15]
            d_s1400 = words[16]

            if dm == '*':
                print('No DM:', name, '; skipping')
                # eg, Fermi-detected pulsars
                continue

            args = dict(name=name,
                        source_type='Pulsar',
                        origin='ATNF Pulsar Cat 2.5.1',
                        ra=float(ra),
                        ra_error=float(d_ra),
                        dec=float(dec),
                        dec_error=float(d_dec),
                        dm=float(dm),
                        dm_error=float(d_dm),
                        )
            if s400 != '*':
                args.update(s400=float(s400),
                            s400_error=float(d_s400))
            if s1400 != '*':
                args.update(s1400=float(s1400),
                            s1400_error=float(d_s1400))
            ks = KnownSource(**args)
            session.add(ks)
            session.flush()

if __name__ == '__main__':
    main()
