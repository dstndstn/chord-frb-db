""" 
This module defines the functions that convert the L2/L3 events into a vector of features for the Machine Learning algorithms to use to classify the RFI and Astro events.

This defines three functions.

1) event_to_features(L2Event, event_no=None)
2) db_to_features(event_no) requires L4 to be installed and accessible.
3) features_to_vector(feature_vector, feature_name_list)

The challenge here is that we try to make machine learning features 
from two different sources, the database entries and the L2 Events, 
each of which stores the header information in slightly different ways. 

Functions 1 and 2 must defined equivalently to make sure that the
training vectors does not differ from actual use. This is a 
responsibility for the maintainer. 

The final vector of features is made by the third function that uses a list of feature names to create the input to the ML predicting or training. If the feature names are not among the return values of the feature list, then an error is raised.

 Currently defined features:

* 'max_coherent_snr': Maximum SNR in the coherent beams. 0 if pure incoherent
* 'incoherent_snr': SNR in the incoherent beam (0 if pure coherent)
* 'max_to_second_snr_ratio': SNR ratio in the brightest to second 
                           brightest coherent detection. Second brightest 
                           SNR is assumed to be 7 if single coherent beam detection.
                           0 if purely incoherent beam detection 
* 'max_level1_grade': Highest L1 grade in the coherent beams else incoherent beam 
* 'mean_level1_grade': Mean L1 grade in the coherent beams else incoherent beam
* 'snr_weighted_level1_grade': SNR weighted average L1 grade in 
                             coherent beams (else incoherent beam)
* 'std_level1_grade': Standard deviation of L1 grades in the coherent beams else incoherent beam
* 'min_tree_index': Minimum tree index in the coherent beams (else incoherent)
* 'mean_tree_index': Mean tree index in the coherent beams else incoherent beam
* 'snr_weighted_tree_index': SNR weighted average tree index in the 
                           coherent beams else incoherent beam
* 'std_tree_index': Standard deviation of the tree indices in the 
                  coherent beams else incoherent beam
* 'beam_activity': Beam activity normalized by the total number of 
                 active coherent beams
* 'ew_extent': East-West extent of the coherent beams, 0 if purely incohernet
* 'ns_extent': North-South extent of the coherent beams, 0 if purely incohernet
* 'group_density' : num_coherent_beams/(ew_extent+1)/(ns_extent+1). 
                    0 if purely incoherent. 1 if single coherentbeam detection.
* 'max_snr_ns_beam': North-South position of the max SNR coherent beam 
                   (if available, else incoherent beam)
* 'coh_dm_activity': Activity at unique DMs in coherent beams 
* 'incoh_dm_activity': Activity at unique DMs in the incoherent beam

Additional items, not used for ML. 
* 'event_no'
* 'time'
* 'dm'
* 'snr': Max of coherent/incoherent SNR (used for plotting)
"""


from builtins import zip
from builtins import range

__author__ = "CHIME FRB Group"
__version__ = "0.1"
__maintainer__ = "Shriharsh Tendulkar"
__developers__ = "Shriharsh Tendulkar"
__email__ = "shriharsh@physics.mcgill.ca"
__status__ = "Epsilon"


import numpy as np
from datetime import datetime as dt
from datetime import timedelta
from pytz import UTC

L4_SETUP = False

try:
    import django

    django.setup()
    from django.db.models import Count, Avg, F, Min, Max
    from l4_databases.apps.astro_events.models import EventRegister, EventDeadBeam, EventBeamHeader
    L4_SETUP = True
except:
    print(
        "Warning: Could not find an L4 installation.\n This is fine unless you are trying to get events from the database."
    )


L1_FEATURE_DTYPE = [
    ("max_coherent_snr", float),
    ("incoherent_snr", float),
    ("max_to_second_snr_ratio", float),
    ("max_level1_grade", float),
    ("mean_level1_grade", float),
    ("snr_weighted_level1_grade", float),
    ("snr_weighted_tree_index_weighted_level1_grade", float),
    ("std_level1_grade", float),
    ("min_tree_index", int),
    ("mean_tree_index", float),
    ("snr_weighted_tree_index", float),
    ("snr_vs_dm", float),
    ("std_tree_index", int),
    ("ew_extent", int),
    ("ns_extent", int),
    ("group_density", float),
    ("max_snr_ns_beam", int),
    ("snr", float),
]

FULL_FEATURE_DTYPE = L1_FEATURE_DTYPE + [
    ("beam_activity", float),
    ("coh_dm_activity", float),
    ("incoh_dm_activity", float),
    ("avg_l1_grade", float),
    ("event_no", int),
    ("time", dt),
    ("dm", float),
]


def print_available_features():
    print("Available features:\n")
    for feature in FULL_FEATURE_DTYPE:
        print((feature[0]))


def check_filter_labels_valid(label_list):
    feature_label_list = []
    for feature in FULL_FEATURE_DTYPE:
        feature_label_list.append(feature[0])

    is_subset = set(label_list).issubset(set(feature_label_list))
    if not is_subset:
        print(
            "Some requested feature label is not defined in the rfi_features definitions. Check this list or modify the code to define new features."
        )
        print_available_features()
    return is_subset


def features_to_vector(features_vector, label_list):
    """
    Creates a floating point vector from the features vector by 
    choosing specific features. The order of the labels is maintained.
    
    Inputs:
    -------
    features_vector : np.recarray
    Numpy record array of features. Length n_samples.
    The dtype is assumed to be FULL_FEATURE_DTYPE.
    
    label_list: list of strings
    List of feature labels to be copied over. Length is n_features.
    Features with the named labels must exist in FULL_FEATURE_DTYPE.
    Use ``check_filter_labels_valid`` to validate.
    Do not give ``time`` as a part of this label list. The function will 
    raise an error if it cannot convert the data to float.

    Outputs:
    --------
    vector_array : numpy array shape =(n_samples, n_features) dtype=float)
    Output array 
    """
    n_samples = len(features_vector)
    n_features = len(label_list)
    ret = np.zeros((n_samples, n_features), dtype=float)

    for i in range(n_features):
        ret[:, i] = features_vector[label_list[i]].astype(float)

    return ret


def event_to_features(event, event_no=None, return_y=False):
    """
    This function generates a vector of features from an L2 event object.
    Not all the features are used by the classifier. 

    Inputs:
    -------

    event : L2Event object
    This can either come from the pipeline or 
    from a pickled file (for offline classification)

    event_no : int or None
    If not None, the returned feature vector has this as its event number.
    Else the event number field is zero.

    return_y : bool
    If True, returns the existing classification based on the L2 grade.
    Used in training but not in pipeline.

    Returns:
    --------
    feature_vector : np.recarray
    This contains the features defined above.
    
    y : 0 or 1
    Classification of the event, if return_y is True.
    """
    ret = np.zeros((1,), dtype=FULL_FEATURE_DTYPE)

    if hasattr(event, "event_no"):
        ret["event_no"] = event.event_no
    if event_no is not None:
        # override the event number provided by the user
        ret["event_no"] = event_no

    ret["dm"] = event.dm
    ret["time"] = event.timestamp_utc

    num_dead_beams = len(event.dead_beams)
    num_active_beams = 1021 - num_dead_beams

    ret["beam_activity"] = float(event.beam_activity) / (num_active_beams)
    if hasattr(event, "dm_activity"):
        ret["coh_dm_activity"] = float(event.dm_activity)
    #if hasattr(event.futures, "incoh_dm_activity"): # don't have this in CHORD L2event!
    #    ret["incoh_dm_activity"] = float(event.futures.incoh_dm_activity)
    if hasattr(event, "avg_l1_grade"):
        ret["avg_l1_grade"] = float(event.avg_l1_grade)

    l1_events = event.l1_events

    l1_features = get_l1_features(l1_events)
    snr_vs_dm_curve = l1_events.snr_vs_dm[np.argmax(l1_events.snr)]
    snr_vs_dm_metric = get_snr_vs_dm_metric(snr_vs_dm_curve, l1_events.tree_index[np.argmax(l1_events.snr)])
    l1_features["snr_vs_dm"] = snr_vs_dm_metric

    for key in l1_features.dtype.fields:
        ret[key] = l1_features[key]

    if return_y:
        y = int(event.rfi_grade_level2 > 5)
        return ret, y

    return ret


def db_to_features(event_no, return_y=False):
    """
    Gets the database entry for a given event no and creates the features vector 
    from it. This requires access to the L4 database. If the access is not possible,
    it will raise an AssertionError.

    Inputs:
    -------
    event_no : long/int
    Event number for which values are to be extracted.

    return_y : bool
    If True, returns the existing classification based on the L2 grade.
    Used in training but not in pipeline.

    Returns:
    --------
    feature_vector : np.recarray
    This contains the features defined above.
    
    y : 0 or 1
    Classification of the event, if return_y is True.
    """
    assert (
        L4_SETUP
    ), "L4 needs to be setup for this function to work. Check your django setup."

    ret = np.zeros((1,), dtype=FULL_FEATURE_DTYPE)

    event = EventRegister.objects.get(event_no__exact=event_no)
    ret["event_no"] = event_no
    ret["time"] = event.timestamp_utc
    try:
        ret["dm"] = float(event.eventmultibeamheaderanalysis_set.latest("event_no").dm)
    except:
        try:
            ret["dm"] = float(event.eventbestdata_set.last().dm)

        except:
            raise KeyError("Could not find a valid DM")

    num_dead_beams = get_dead_beams(event_no)
    num_active_beams = 1021 - num_dead_beams
    ret["beam_activity"] = float(event.beam_activity) / (num_active_beams)
    ret["coh_dm_activity"], ret["incoh_dm_activity"], ret["avg_l1_grade"] = get_dm_activity(
        event.timestamp_utc,
        event_no=event_no
    )
    l1_events = get_l1_events(event)
    snr_vs_dm = get_snr_vs_dm(event_no)
    l1_features = get_l1_features(l1_events)
    snr_vs_dm_metric = get_snr_vs_dm_metric(snr_vs_dm, l1_events['tree_index'][np.argmax(l1_events['snr'])])
    l1_features["snr_vs_dm"] = snr_vs_dm_metric

    for key in list(l1_features.dtype.fields.keys()):
        ret[key] = l1_features[key]

    if return_y:
        y = int(event.rfi_grade_level2 > 5)
        return ret, y

    return ret


def get_dead_beams(event_no):
    """
    Gets the number of dead beams corresponding to a particular event.

    Inputs:
    -------
    event_no : long/int
    
    Returns:
    --------
    num_dead_beams : int
    Number of dead beams.

    """
    try:
        dead_beam_entry_event = EventDeadBeam.objects.filter(
            event_no__lte=event_no
        ).latest("event_no")
    except:
        print("Could not find dead beam entry lower range.")
        print(" Are there no events before this one in the EventDeadBeam table?")
        raise KeyError

    return EventDeadBeam.objects.filter(
        event_no__exact=dead_beam_entry_event.event_no
    ).count()

def get_nearby_qs(event_no, start, utc_time):
    min_event_no = event_no-500
    max_event_no = event_no+500
    qs = EventBeamHeader.objects.filter(event_no__gte=min_event_no, event_no__lte=max_event_no).order_by('timestamp_utc')
    while qs[0].timestamp_utc > start:
        qs = EventBeamHeader.objects.filter(event_no__gte=min_event_no - 500, event_no__lte=max_event_no).order_by('timestamp_utc')
        min_event_no = min_event_no - 500
    while qs[len(qs)-1].timestamp_utc < utc_time:
        qs = EventBeamHeader.objects.filter(event_no__gte=min_event_no, event_no__lte=max_event_no+500).order_by('timestamp_utc')
        max_event_no = max_event_no + 500
    events_to_include = []
    for q in qs:
        if start <= q.timestamp_utc <= utc_time:
            events_to_include.append(q.event_no)
    events_to_include = list(set(events_to_include))       
    return EventBeamHeader.objects.filter(event_no__in=events_to_include)

def get_dm_activity(utc_time, chunk_size=8.0, event_no=None):
    """
    Calculates the coherent and incoherent DM activity for a given event.
    This is an approximation since the exact value depends on where 
    the event lies in the time chunk.

    Inputs:
    -------
    utc_time : dt
    Datetime object with the timestamp of the event

    chunk_size : float, seconds
    Size of the chunk to be used for calculating the activity.

    Outputs:
    --------
    coh_dm_activity, incoh_dm_activity: ints
    The number of unique DM events in the coherent and incoherent beams 
    in the time chunk.
    """
    # gets the dm activity for a particular event number.
    start = utc_time - timedelta(0, chunk_size / 2.0)
    end = utc_time + timedelta(0, chunk_size / 2.0)
    if event_no:
        qs = get_nearby_qs(event_no, start, utc_time)            
    else:
        qs = EventBeamHeader.objects.filter(timestamp_utc__range=(start, utc_time))
    coh_qs = qs.filter(is_incoherent__exact=False)
    incoh_qs = qs.filter(is_incoherent__exact=True)
    try:
        coh_dms = np.core.records.fromrecords(coh_qs.values_list("dm"))
        l1_grades = np.core.records.fromrecords(coh_qs.values_list("rfi_grade_level1"))
        coh_dm_activity = len(np.unique(coh_dms))
        avg_l1_grade = np.mean([l[0] for l in l1_grades])
    except IndexError:
        coh_dm_activity = 0
        avg_l1_grade = 0

    try:
        incoh_dms = np.core.records.fromrecords(incoh_qs.values_list("dm"))
        incoh_dm_activity = len(np.unique(incoh_dms))
    except IndexError:
        incoh_dm_activity = 0
    return coh_dm_activity, incoh_dm_activity, avg_l1_grade


def get_l1_events(event):
    """
    Gets the L1 events for a given event no as a numpy record array.
    Currently, this only gets the fields that are relevant to the RFI Sifter.

    Inputs:
    -------

    event : EventRegister model object
    Event object returned by the database.

    Outputs:
    --------

    l1_events : np.recarray

    """
    l1_args = ["beam", "snr", "rfi_grade_level1", "tree_index", "is_incoherent"]
    l1_args_types = [int, float, float, int, bool]

    l1_args_dtype = list(zip(l1_args, l1_args_types))
    l1_events = np.core.records.fromrecords(
        event.eventbeamheader_set.values_list(*l1_args), dtype=l1_args_dtype
    )

    return l1_events

def get_snr_vs_dm(event_no):
    l1_args = ["snr", "eventbeamplotdata__y_s", "eventbeamplotdata__plot_type"]
    qs = EventBeamHeader.objects.filter(event_no__exact = event_no)
    data = qs.values_list(*l1_args)
    snr_vs_dm = []
    snr = 0
    for d in data:
        if d[2] == 'SNR_VS_DM' and d[0] >= snr:
            snr_vs_dm = d[1]
            snr = d[0]
    snr_vs_dm = snr_vs_dm.split(',')
    snr_vs_dm = np.asarray([float(s) for s in snr_vs_dm])
        
    return snr_vs_dm[snr_vs_dm >0] 

def get_snr_vs_dm_metric(snr_vs_dm, tree_index):
    snr_vs_dm = snr_vs_dm[snr_vs_dm>0]
    #15 is the average DM span
    dm_span = {0:6.8, 1:6.8, 2:15, 3:15, 4:15, 5:26}
    metric = (max(snr_vs_dm)-min(snr_vs_dm[0], snr_vs_dm[-1]))/(dm_span.get(tree_index)*max(snr_vs_dm))
    return metric

def get_l1_features(l1_events):
    """
    Gets features from the L1 event headers. This code is common to
    ``event_to_features`` and ``db_to_features`` functions.
    This will return a subset of the features provided by L1_FEATURE_DTYPE.

    Inputs:
    -------

    l1_events : np.recarray
    This must have the subset of the fields of L1_HDR_DTYPE 
    (defined in frb_common), that are required for calculating the features.

    Outputs:
    --------
    l1_features : np.recarray
    Numpy record array of L1_FEATURE_DTYPE dtype.

    """

    ret = np.zeros((1,), dtype=L1_FEATURE_DTYPE)

    num_beams = len(l1_events)
    num_incoherent_beams = np.count_nonzero(l1_events["is_incoherent"])
    num_coherent_beams = num_beams - num_incoherent_beams

    ret["snr"] = np.max(l1_events["snr"])
    # penalty on L1b score for high trees
    tree_weight = {
        0: 1,
        1: 1,
        2: 1,
        3: 1.5,
        4: 2,
        5: 3}

    if num_coherent_beams == 0:  # this is a purely incoherent beam event
        ret["max_coherent_snr"] = 0.0
        ret["incoherent_snr"] = np.max(l1_events["snr"])
        ret["max_to_second_snr_ratio"] = 0.0
        ret["max_level1_grade"] = np.max(l1_events["rfi_grade_level1"])
        ret["mean_level1_grade"] = np.mean(l1_events["rfi_grade_level1"])
        ret["snr_weighted_level1_grade"] = np.average(
            l1_events["rfi_grade_level1"], weights=l1_events["snr"]
        )
        ret["std_level1_grade"] = 0
        ret["min_tree_index"] = np.min(l1_events["tree_index"])
        ret["mean_tree_index"] = np.mean(l1_events["tree_index"])
        ret["snr_weighted_tree_index"] = np.average(
            l1_events["tree_index"], weights=l1_events["snr"]
        )
        ret["snr_weighted_tree_index_weighted_level1_grade"] = [ret["snr_weighted_level1_grade"][0]/ tree_weight.get(ret["min_tree_index"][0])]
        ret["std_tree_index"] = 0.0
        ret["ew_extent"] = 0
        ret["ns_extent"] = 0
        ret["group_density"] = 0
        ret["max_snr_ns_beam"] = 0

    else:
        # there exist coherent beams.
        # incoherent beam may or may not exist
        if num_incoherent_beams > 0:
            incoherent_beam_idxs = np.where(l1_events["is_incoherent"])
            ret["incoherent_snr"] = np.max(l1_events[incoherent_beam_idxs]["snr"])
        else:
            ret["incoherent_snr"] = 0.0

        l1_events = l1_events[np.where(l1_events["is_incoherent"] == False)]

        beam_nos = l1_events["beam"]
        snr_sort = np.argsort(l1_events["snr"])

        ret["max_coherent_snr"] = l1_events["snr"][snr_sort[-1]]

        if num_coherent_beams > 1:
            second_max_snr = l1_events["snr"][snr_sort[-2]]
        else:
            second_max_snr = 7.0
        ret["max_to_second_snr_ratio"] = ret["max_coherent_snr"] / second_max_snr

        ret["max_level1_grade"] = np.max(l1_events["rfi_grade_level1"])
        ret["mean_level1_grade"] = np.mean(l1_events["rfi_grade_level1"])
        ret["snr_weighted_level1_grade"] = np.average(
            l1_events["rfi_grade_level1"], weights=l1_events["snr"]
        )
        ret["std_level1_grade"] = np.std(l1_events["rfi_grade_level1"])
        ret["min_tree_index"] = np.min(l1_events["tree_index"])
        ret["mean_tree_index"] = np.mean(l1_events["tree_index"])
        ret["snr_weighted_tree_index"] = np.average(
            l1_events["tree_index"], weights=l1_events["snr"]
        )
        ret["std_tree_index"] = np.std(l1_events["tree_index"])
        ret["snr_weighted_tree_index_weighted_level1_grade"] = [ret["snr_weighted_level1_grade"][0]/ tree_weight.get(ret["min_tree_index"][0])]
        ns_beams = l1_events["beam"] % 1000
        ew_beams = l1_events["beam"] // 1000
        ret["ns_extent"] = np.max(ns_beams) - np.min(ns_beams)
        ret["ew_extent"] = np.max(ew_beams) - np.min(ew_beams)
        ret["group_density"] = (
            float(len(l1_events)) / (ret["ns_extent"] + 1) / (ret["ew_extent"] + 1)
        )
        ret["max_snr_ns_beam"] = ns_beams[snr_sort[-1]]

    return ret
