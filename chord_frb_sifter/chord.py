import numpy as np

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

    def grid_to_topocentric(self, x, y):
        '''
        "grid" coordinates: aligned with the dish spacings;
        X is E/W separation,
        Y is N/S separation.

        Returns topocentric coordinates - which are aligned with lat/long,
        but local to site.
        X is East
        Y is North
        '''
        #scalar = np.isscalar(x + y)
        # Transpose for inverse
        ze = np.zeros_like(x+y)
        xyz = np.stack((x+ze, y+ze, ze))
        print('xyz shape', xyz.shape)
        topo = np.matmul(self.R_topo_to_grid.T, xyz)
        return topo

    def topocentric_to_itrs(self, vec):
        # Inverse transform, use R transpose.
        v_itrs = np.matmul(self.R_itrs_to_topo.T, vec)
        return v_itrs

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
        topo = chord.grid_to_topocentric(x, y)
        print('x,y', x,y, '-> topo:')
        print(topo)
        print('-> ITRS:')
        itrs = chord.topocentric_to_itrs(topo)
        print(itrs)
    
