"""
Definition of L1 and L2 event classes.

Both L1Event and L2Event are a dictionary with the ability to
manipulate dictiionary items as class attributes.
"""
import numpy as np

class AttribDict(dict):
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    _reserved = set(dir(dict))
    
    def __getattr__(self, name):
        if name in self._reserved:
            return super().__getattribute__(name)
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        if name.startswith("_") or name in self._reserved:
            raise AttributeError(f"'{name}' is reserved")
        self[name] = value


class EventGroup(AttribDict):
    pass

        

# def get_L1Event_dtype():
# 
#     # Hardcoded for now to avoid loading CHIME bonsai config.
#     # Will want to replace with CHORD config loading eventually.
#     nds = [1, 2, 4, 8, 16]
#     nbeta = 2
# 
#     # The dtype from the saved L1b triggers from fits files:
#     #dtype([
#     # ('frame0_nano', '>i8'), 
#     # ('beam', '>i8'), 
#     # ('fpga', '>i8'), 
#     # ('beam_no', '>f8'), 
#     # ('timestamp_utc', '>f8'), 
#     # ('timestamp_fpga', '>f8'), 
#     # ('tree_index', 'u1'), 
#     # ('snr', '>f4'), 
#     # ('snr_scale', '>f4'), 
#     # ('dm', '>f4'), 
#     # ('spectral_index', 'u1'), 
#     # ('scattering_measure', 'u1'), 
#     # ('level1_nhits', '>f8'), 
#     # ('rfi_grade_level1', 'u1'), 
#     # ('rfi_mask_fraction', '>f4'), 
#     # ('rfi_clip_fraction', '>f4'), 
#     # ('snr_vs_dm', '>f4', (17,)), 
#     # ('snr_vs_tree_index', '>f4', (5,)), 
#     # ('snr_vs_spectral_index', '>f4', (2,))]
# 
#     # These are fields that Dustin has in the list of dicts l1 events
#     l1_dtype = np.dtype([
#         ("id", np.uint64),
#         ("beam", np.uint16),
#         ("timestamp_utc", np.float64),
#         ("timestamp_fpga", np.uint64),
#         ("frame0_nano", np.uint64),
#         ("chunk_fpga", np.uint64),
#         ("chunk_utc", np.float64),
#         ("tree_index", np.uint8),
#         ("snr", np.float32),
#         ("snr_scale", np.float32),
#         ("dm", np.float32),
#         ("dm_error", np.float32),
#         ("spectral_index", np.uint8),
#         ("scattering_measure", np.uint8),
#         ("level1_nhits", np.uint16),
#         ("rfi_grade_level1", np.uint8),
#         ("rfi_mask_fraction", np.float32),
#         ("rfi_clip_fraction", np.float32),
#         ("snr_vs_dm", np.float32, 17),
#         ("snr_vs_tree_index", np.float32, len(nds)),
#         ("snr_vs_spectral_index", np.float32, nbeta),
#         ("beam_grid_x", np.float32),
#         ("beam_grid_y", np.float32),
#         ("beam_dra", np.float32),
#         ("beam_ddec", np.float32),
#         ("pipeline_timestamp", np.float32),
#         ("pipeline_id", np.uint64),
#         ("is_incoherent", bool),
#     ])
# 
#     return l1_dtype

class L1Event(AttribDict):
    # """
    # A class representing an L1 event, inheriting from numpy recarray.
    # """
    # def __new__(cls, input_array):
    # 
    #     # hack for list of dicts (not sure if we want to support long-term though).
    #     if isinstance(input_array, list) and isinstance(input_array[0], dict):
    #         array = np.zeros(len(input_array),dtype=get_L1Event_dtype())
    #         for k in input_array[0].keys():
    #             array[k] = [item[k] for item in input_array]
    # 
    #     else:
    #         # Casts the input as a numpy recarray with the L1Event dtype
    #         # May want to add other ways to create?
    #         array = np.asarray(input_array,dtype=get_L1Event_dtype())
    #     return array.view(cls)

    def database_payload(self):
        # my name -> db name
        l1_name_map = {
            'id': True,
            'beam_id': 'beam',
            'snr': True,
            'fpga_timestamp': 'timestamp_fpga',
            'timestamp_utc': True,
            #'time_error': True,
            'tree_index': True,
            'rfi_grade_level1': 'rfi_grade',
            #'rfi_mask_fraction': True,
            #'rfi_clip_fraction': True,
            'dm': True,
            'dm_error': True,
            #'ra': True,
            #'ra_error': True,
            #'dec': True,
            #'dec_error': True,
        }

        db_args = {}
        for key,val in self.items():
            #if key == 'timestamp_utc':
            #    # microsec -> sec
            #    val *= 1e-6
            val = to_db_type(val)
            k2 = l1_name_map.get(key, None)
            if k2 is not None:
                # same key name
                if k2 is True:
                    k2 = key
                db_args[k2] = val

        ## FIXME -- fake up some required fields!
        for key in ['time_error', 'rfi_mask_fraction', 'rfi_clip_fraction',
                    'ra','dec', 'ra_error', 'dec_error']:
            if not key in db_args:
                db_args[key] = 0.

        return db_args

class L2Event(AttribDict):
    def is_rfi(self):
        return getattr(self, 'flag_rfi', False)
    def is_frb(self):
        return getattr(self, 'flag_frb', False)
    def is_galactic(self):
        return getattr(self, 'flag_galactic', False)
    def is_ambiguous(self):
        return getattr(self, 'flag_ambiguous', False)
    def is_known_source(self):
        return getattr(self, 'flag_known_source', False)

    def set_frb(self):
        self.flag_frb = True
    def set_ambiguous(self):
        self.flag_ambiguous = True
    def set_galactic(self):
        self.flag_galactic = True

    def database_payload(self):
        # dict shallow copy
        #payload = self.copy()
        l2_db_args = { 'is_rfi': self.is_rfi(),
                       'is_known_pulsar': False,
                       'is_new_burst': False,
                       'is_frb': self.is_frb(),
                       'is_repeating_frb': False,
                       'scattering': 0.,
                       'fluence': 0.,
        }
        l2_name_map = {
            'event_id': True,
            'timestamp_utc': 'timestamp',
            'combined_snr': 'total_snr',
            'dm': True,
            'dm_error': True,
            'ra': True,
            'dec': True,
            'is_rfi': True,
            'is_frb': True,
            'pos_ra_deg': 'ra',
            'pos_error_semimajor_deg_68': 'ra_error',
            'pos_dec_deg': 'dec',
            'pos_error_semiminor_deg_68': 'dec_error',
            'dm_gal_ne_2001_max': 'dm_ne2001',
            'dm_gal_ymw_2016_max': 'dm_ymw2016',
            'spectral_index': True,
            'pulse_width_ms': 'pulse_width',
            'rfi_grade_level2': 'rfi_grade',
            'beam_activity': True,
            'flux_mjy': 'flux',
        }

        n_l1 = 0
        for k,v in self.items():
            # skip...
            if k in ['dead_beam_nos']:
                continue
            if k == 'l1_events':
                n_l1 = len(v)
                continue

            # FIXME
            if k == 'known_source_name':
                if v != "":
                    print('Known source!')
                    print('val: "%s"' % v)

            v = to_db_type(v)
            if k == 'timestamp_utc':
                # microseconds -> seconds
                v *= 1e-6
            if k == 'flux_mjy':
                # milli -> Jansky
                v *= 0.001

            k2 = l2_name_map.get(k, None)
            if k2 is not None:
                # same key name
                if k2 is True:
                    k2 = k
                l2_db_args[k2] = v
            else:
                pass
                #print('Ignoring L2 key:', k, '=', v)

        l2_db_args['nbeams'] = n_l1
        return l2_db_args


def to_db_type(v):
    # convert to normal python types for database interaction
    if isinstance(v, (np.float32, np.float64)):
        v = float(v)
    if isinstance(v, (np.uint64, np.uint16, np.uint8)):
        v = int(v)
    return v
