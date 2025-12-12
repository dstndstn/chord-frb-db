"""
Definition of L1 and L2 event classes.

L1Event is a numpy recarray with fields corresponding to the output of the L1 
search. 

L2Event is a dictionary with the ability to manipulate dictiionary items as 
class attributes.
"""

import numpy as np

def get_L1Event_dtype():

    # Hardcoded for now to avoid loading CHIME bonsai config.
    # Will want to replace with CHORD config loading eventually.
    nds = [1, 2, 4, 8, 16]
    nbeta = 2

    # The dtype from the saved L1b triggers:
    #dtype([
    # ('frame0_nano', '>i8'), 
    # ('beam', '>i8'), 
    # ('fpga', '>i8'), 
    # ('beam_no', '>f8'), 
    # ('timestamp_utc', '>f8'), 
    # ('timestamp_fpga', '>f8'), 
    # ('tree_index', 'u1'), 
    # ('snr', '>f4'), 
    # ('snr_scale', '>f4'), 
    # ('dm', '>f4'), 
    # ('spectral_index', 'u1'), 
    # ('scattering_measure', 'u1'), 
    # ('level1_nhits', '>f8'), 
    # ('rfi_grade_level1', 'u1'), 
    # ('rfi_mask_fraction', '>f4'), 
    # ('rfi_clip_fraction', '>f4'), 
    # ('snr_vs_dm', '>f4', (17,)), 
    # ('snr_vs_tree_index', '>f4', (5,)), 
    # ('snr_vs_spectral_index', '>f4', (2,))]

    # so far for the CHIME-event testbed just use the base (i.e whats from L1b) 
    # fields?
    l1_dtype = np.dtype([
        ("beam_no", np.uint16),
        ("timestamp_utc", "datetime64[us]"),
        ("timestamp_fpga", np.uint64),
        ("chunk_fpga", np.uint64),
        ("tree_index", np.uint8),
        ("snr", np.float32),
        ("snr_scale", np.float32),
        ("dm", np.float32),
        ("spectral_index", np.uint8),
        ("scattering_measure", np.uint8),
        ("level1_nhits", np.uint16),
        ("rfi_grade_level1", np.uint8),
        ("rfi_mask_fraction", np.float32),
        ("rfi_clip_fraction", np.float32),
        ("snr_vs_dm", np.float32, 17),
        ("snr_vs_tree_index", np.float32, len(nds)),
        ("snr_vs_spectral_index", np.float32, nbeta),
    ])

    return l1_dtype

class L1Event(np.recarray):
    """
    A class representing an L1 event, inheriting from numpy recarray.
    """
    def __new__(cls, input_array):

        # Casts the input as a numpy recarray with the L1Event dtype
        # May want to add other ways to create?
        obj = np.asarray(input_array,dtype=get_L1Event_dtype()).view(cls)
        return obj

class L2Event(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__