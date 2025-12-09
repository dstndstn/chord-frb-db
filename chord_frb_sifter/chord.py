import numpy as np
from astropy.coordinates import SkyCoord, EarthLocation
from astropy.time import Time
import astropy.units as u

class Telescope(object):
    pass

class Chord(Telescope):
    # With reference to Geoff Ryan's document on CHORD coordinate systems,
    # specifically Fig 6;
    # https://www.overleaf.com/project/655bb79463f7ccf32c834e5d
    # This reproduces functions in kotekan:
    # https://github.com/kotekan/kotekan/blob/chord/lib/utils/CHORDTelescope.cpp

    def __init__(self, conf):
        self.sep_x = conf.get('grid_x_axis', [1., 0., 0.])
        self.sep_y = conf.get('grid_y_axis', [0., 1., 0.])
        self.sep_z = np.cross(self.sep_x, self.sep_y)

        # Construct the topocentric -> grid rotation matrix.
        # We assume the inverse is the transpose.
        # row 0 = sep_x, etc
        self.R_topo_to_grid = np.vstack((self.sep_x, self.sep_y, self.sep_z))

        self.origin_itrs_lon_deg = conf.get('origin_itrs_lon_deg', 0.0)
        self.origin_itrs_lat_deg = conf.get('origin_itrs_lat_deg', 0.0)
        #self.dish_coelev_deg = conf.get('dish_coelev_deg', 0.0)
        print('Config file: lat/long', self.origin_itrs_lat_deg, self.origin_itrs_lon_deg, 'deg')
        self.location = EarthLocation(lat=self.origin_itrs_lat_deg * u.deg,
                                      lon=self.origin_itrs_lon_deg * u.deg)

        sin_lon = np.sin(np.deg2rad(self.origin_itrs_lon_deg))
        cos_lon = np.cos(np.deg2rad(self.origin_itrs_lon_deg))
        sin_lat = np.sin(np.deg2rad(self.origin_itrs_lat_deg))
        cos_lat = np.cos(np.deg2rad(self.origin_itrs_lat_deg))

        self.R_itrs_to_topo = np.array([
            # Topocentric X (East) in ITRS (Earth-centered, Earth-fixed) coords            
            [-        sin_lon,          cos_lon, 0.],
            # Topocentric Y (North) in ITRS (Earth-centered, Earth-fixed) coords
            [-sin_lat*cos_lon, -sin_lat*sin_lon, cos_lat],
            # Topocentric Z (Up) in ITRS (Earth-centered, Earth-fixed) coords
            [ cos_lat*cos_lon,  cos_lat*sin_lon, sin_lat]
        ])

    def grid_to_topocentric(self, x, y, z=None):
        '''
        "grid" coordinates: aligned with the dish spacings;
        X is E/W separation,
        Y is N/S separation.

        Returns topocentric coordinates - which are aligned with lat/long,
        but local to site.
        X is East
        Y is North
        '''
        # Transpose for inverse
        if z is None:
            # get z the right shape for broadcasting
            # assume z = 0...
            z = np.zeros_like(x+y)
            x = x + z
            y = y + z
        xyz = np.stack((x, y, z))
        #print('xyz shape', xyz.shape)
        topo = np.matmul(self.R_topo_to_grid.T, xyz)
        return topo

    def topocentric_to_itrs(self, vec):
        # Inverse transform, use R transpose.
        v_itrs = np.matmul(self.R_itrs_to_topo.T, vec)
        return v_itrs

    def itrs_to_radec(self, itrs, time):
        '''
        "time": astropy Time object

        Returns (ra, dec) in degrees.
        '''
        sc = SkyCoord(x=itrs[0], y=itrs[1], z=itrs[2], representation_type='cartesian',
                      obstime=time, frame='itrs', location=self.location)
        icrs = sc.transform_to('icrs')
        return (icrs.ra.deg, icrs.dec.deg)

    def grid_to_radec(self, x, y, z, time):
        topo = self.grid_to_topocentric(x, y, z)
        itrs = self.tocentric_to_itrs(topo)
        rd = self.itrs_to_radec(itrs, time)
        return rd

if __name__ == '__main__':
    import yaml
    try:
        from yaml import CLoader as Loader, CDumper as Dumper
    except ImportError:
        from yaml import Loader, Dumper

    import os

    conf = yaml.load(open(os.path.join(os.path.dirname(__file__), 'config', 'testChordTelescope.yaml'),
                          'r'), Loader=Loader)
    tele = conf['telescope']
    chord = Chord(tele)

    for x,y in [(0., 0.),
                (0., 1.),
                (1., 1.),
                (np.array([0., 1., 2.]), 0),
                (np.array([0., 1., 2.]), np.array([3,4,5])),
                ]:
        print()
        topo = chord.grid_to_topocentric(x, y)
        print('x,y', x,y, '-> topo:')
        print(topo)
        print('-> ITRS:')
        itrs = chord.topocentric_to_itrs(topo)
        print(itrs)

        t0 = Time('2026-01-01T00:00:00Z', scale='utc')
        #dt = np.linspace(0, 365.2425, 100) * u.day
        #t = t0 + dt
        t = t0
        print('x', itrs[0])
        print('y', itrs[1])
        print('z', itrs[2])
        sc = SkyCoord(x=itrs[0], y=itrs[1], z=itrs[2], representation_type='cartesian',
                      obstime=t, frame='itrs')

        print('sky coord:', sc)
        cirs = sc.transform_to('cirs')
        print('cirs:', cirs)
        


    x,y = 1.,0.
    topo = chord.grid_to_topocentric(x, y)
    itrs_x = chord.topocentric_to_itrs(topo)
    x,y = 0.,1.
    topo = chord.grid_to_topocentric(x, y)
    itrs_y = chord.topocentric_to_itrs(topo)

    itrs_z = np.cross(itrs_x, itrs_y)
    itrs = itrs_z

    # Look a bit north -- so there's a + projection onto the y axis.
    y = np.sin(np.deg2rad(5.))
    x = 0.
    z = np.sqrt(1. - x**2 - y**2)
    topo = chord.grid_to_topocentric(x, y, z=z)
    itrs2 = chord.topocentric_to_itrs(topo)

    # Look a bit east -- so there's a + projection onto the x axis.
    y = 0.
    x = np.sin(np.deg2rad(5.))
    z = np.sqrt(1. - x**2 - y**2)
    topo = chord.grid_to_topocentric(x, y, z=z)
    itrs3 = chord.topocentric_to_itrs(topo)

    location = EarthLocation(lat=chord.origin_itrs_lat_deg, lon=chord.origin_itrs_lon_deg)
    #print('Location', location)
    #location=None

    t = t0
    sc = SkyCoord(x=itrs[0], y=itrs[1], z=itrs[2], representation_type='cartesian',
                  obstime=t, frame='itrs', location=location)
    print('sky coord:', sc)
    cirs = sc.transform_to('cirs')
    print('cirs:', cirs)
    icrs = sc.transform_to('icrs')
    print('icrs:', icrs)

    from astropy.coordinates import AltAz
    
    ra,dec = [],[]
    datetm = []

    ra_aa,dec_aa = [],[]

    ra2,dec2 = [],[]
    ra3,dec3 = [],[]

    ra4,dec4 = [],[]

    t0 = Time('2026-01-01T00:00:00Z', scale='utc')
    #dt = np.linspace(0, 365.2425, 100) * u.day
    dt = np.linspace(0, 1, 100)
    for dti in dt:
        t = t0 + dti * u.day
        sc = SkyCoord(x=itrs[0], y=itrs[1], z=itrs[2], representation_type='cartesian',
                      obstime=t, frame='itrs', location=location)
        icrs = sc.transform_to('icrs')
        ra.append(icrs.ra.deg)
        dec.append(icrs.dec.deg)
        datetm.append(t.to_datetime())

        sc = SkyCoord(x=itrs2[0], y=itrs2[1], z=itrs2[2], representation_type='cartesian',
                      obstime=t, frame='itrs', location=location)
        icrs = sc.transform_to('icrs')
        ra2.append(icrs.ra.deg)
        dec2.append(icrs.dec.deg)

        sc = SkyCoord(x=itrs3[0], y=itrs3[1], z=itrs3[2], representation_type='cartesian',
                      obstime=t, frame='itrs', location=location)
        icrs = sc.transform_to('icrs')
        ra3.append(icrs.ra.deg)
        dec3.append(icrs.dec.deg)

        r,d = chord.itrs_to_radec(itrs3, t)
        ra4.append(r)
        dec4.append(d)

        sc = SkyCoord(alt=90. * u.deg, az=0. * u.deg, frame='altaz',
                      obstime=t, location=location)
        icrs = sc.transform_to('icrs')
        ra_aa.append(icrs.ra.deg)
        dec_aa.append(icrs.dec.deg)

    import matplotlib
    matplotlib.use('Agg')
    import pylab as plt
    
    plt.clf()
    #plt.plot(datetm, ra, '-', label='RA (deg)')
    #plt.plot(datetm, dec, '-', label='Dec (deg)')
    plt.plot(dt, ra, '-', label='zhat RA (deg)')
    plt.plot(dt, dec, '-', label='zhat Dec (deg)')
    plt.plot(dt, ra2, '-', label='North RA (deg)')
    plt.plot(dt, dec2, '-', label='North Dec (deg)')
    plt.plot(dt, ra3, '-', label='East RA (deg)')
    plt.plot(dt, dec3, '-', label='East Dec (deg)')
    plt.plot(dt, ra4, '--', label='East RA (deg)')
    plt.plot(dt, dec4, '--', label='East Dec (deg)')
    plt.plot(dt, ra_aa, '--', label='Up RA (deg)')
    plt.plot(dt, dec_aa, '--', label='Up Dec (deg)')
    plt.legend()
    plt.xlabel('Time')
    plt.savefig('rd.png')
    
