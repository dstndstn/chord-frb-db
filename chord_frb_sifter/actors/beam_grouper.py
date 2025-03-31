"""
This a CHORD/FRB prototype, modified from the CHIME/FRB code.

It groups L1 events in DM, time, and position.
Grouped events form a candidate L2 event.
"""

import time
import json
import traceback
import pickle as pickle
from subprocess import check_output
from collections import deque

import numpy as np
from scipy.spatial import cKDTree
import msgpack

from frb_common import ActorBaseClass
from frb_common import configuration_manager as cm
from frb_common.events import L1Event

__author__ = "CHIME FRB Group"
__developers__ = "Alex Josephy"
__email__ = "alexander.josephy@mail.mcgill.ca"

class BeamGrouper(ActorBaseClass):
    """
    The purpose of this class is to group together L1 events detected in
    different beams that were presumably caused by a common incident pulse.
    These multibeam detections may arise from very bright astrophysical bursts
    as well as near-field RFI.

    Parameters
    ----------
    t_thr, dm_thr, ra_thr, dec_thr : float
        Thresholds in ms, pc cm :sup:`-3`, and beam separation
    **kwargs : dict, optional
        Additional parameters are used to initialize superclass
        (``ActorBaseClass``).

    Extended Summary
    ----------------
    A group is defined as a number of L1 events where, for any event in
    the group, there exists another event whose differences in DM, time,
    RA, and Dec are all below the specified thresholds.

    The grouping is done with the DBSCAN algorithm :sup:`[1,2]`. To use this
    method, we need to first define what a *distance* between different events
    means.  To do this, we first scale the aforementioned axes by dividing the
    values by the relevant thresholds. We then apply the Chebyshev metric
    :sup:`[3]` to get a meaningful distance. The above group definition now
    ensures that, for every event in a group, there exists another event such
    that the *distance* between them is less than 1.

    See Also
    --------
    frb_L2_L3.BeamBuffer :
        The intended upstream actor :ref:`(link) <L1_L2_buffer_doc_page>`

    frb_L2_L3.RFISifter :
        The intended downstream actor :ref:`(link) <L2_rfi_sifter_doc_page>`

    frb_common.ActorBaseClass :
        The superclass :ref:`(link) <actor_base_class_doc_page>`

    frb_common.WorkerProcess :
        The usual wrapper class :ref:`(link) <pipeline_tools_doc_page>`

    References
    ----------
    [1] Ester, M., Kriegel, H.P., Sander, J., & Xu, X. A density-based
    algorithm for discovering clusters in large spatial databases with
    noise. 1996, Proc. 2nd Int. Conf. on Knowledge Discovery and Data
    Mining (Portland, OR: AAAI Press), 226

    [2] `DBSCAN <https://en.wikipedia.org/wiki/DBSCAN>`_

    [3] `Chebyshev Metric <https://en.wikipedia.org/wiki/Chebyshev_distance>`_
    """
    def __init__(self, t_thr, dm_thr, ra_thr, dec_thr, **kwargs):
        super().__init__(**kwargs)
        self.thresholds = [t_thr, dm_thr, ra_thr, dec_thr]
        self.dm_activity_lookback = deque([0] * 10, maxlen=10)
        self.beam_activity_lookback = deque([0] * 10, maxlen=10)

    def perform_action(self, item):
        """Pipeline function that groups L1 events.

        Parameters
        ----------
        item : list
            The first element is a list of currently dead beams, serialized via
            ``msgpack.packb()``.  This list is not actually used within the
            grouping algorithm, but is appended to any ``L2Event``s that are
            generated.  The second element is the L1 events, serialized via
            ``ndarray.tostring()``. Serialized input is the normal pipeline
            behaviour, but unserialized input is accepted as well and will
            result in unserialized output.

        Returns
        -------
        list of ``L2Event`` or list of str
            Element type is chosen to match input. If strings are used, they
            the are the result of a ``cPickle.dumps()`` call.

        """

        print('BeamGrouper: perform_action:', ('%i events' % len(item) if item is not None else 'none'))
        
        try:
            groups = self._attempt_perform_action(item)
            self.PROCESS_STATUS.labels(status="success", actor=self.process_name).inc()
            return groups
        except:  # pylint: disable=broad-except
            self.PROCESS_STATUS.labels(status="failure", actor=self.process_name).inc()
            self.logger.error(traceback.format_exc())
            return None

    def _attempt_perform_action(self, item):
        """ perform_action helper function """
        dead_beam_nos, evts = item
        #self.print('Beam grouper: events: %s' % (str(evts)[:100]))
        serialized_input = isinstance(evts, (bytes, str))
        if serialized_input:
            dead_beam_nos = msgpack.unpackb(dead_beam_nos, use_list=True)
            events = L1Event(evts).copy()
            events.setflags(write=True)

        if len(events) is 0:
            return None
        #self.print('Beam grouper: parsed events', events)
        #self.print('Beam grouper: timestamps: %s' % str(events['pipeline_timestamp'][:])[:100])

        ## ??? shouldn't need this at this point
        if self.frame0_ctime_us:
            new_vals = np.array(2.56 * events.timestamp_fpga + self.frame0_ctime_us, dtype="int")
            events.timestamp_utc[:] = new_vals

        is_incoh = np.in1d(events.beam_no, self.incoherent_beam_ids)
        coh_events = events[~is_incoh]
        incoh_events = (
            events[(is_incoh) & (events.beam_no == events[is_incoh].beam_no.min())]
            if is_incoh.any()
            else events[is_incoh]
        )

        groups = self._cluster(coh_events) if len(coh_events) else []
        groups = self._cluster_with_incoh(groups, incoh_events)

        # remove injection beams to keep RFI metrics clean
        coh_events = coh_events[coh_events.beam_no // 10000 == 0]
        incoh_events = incoh_events[incoh_events.beam_no // 10000 == 0]

        beam_activity = len(np.unique(coh_events.beam_no))
        coh_dm_activity = len(np.unique(coh_events.dm))
        incoh_dm_activity = len(np.unique(incoh_events.dm))
        avg_l1_grade = np.mean(coh_events.rfi_grade_level1)
        self.dm_activity_lookback.append(coh_dm_activity)
        self.beam_activity_lookback.append(beam_activity)

        # self.print('BeamGrouper: producing groups:', len(groups))
        # self.print('BeamGrouper: group timestamps:', ', '.join([str(g['pipeline_timestamp'][:])[:100]
        # for g in groups]))
        tnow = time.monotonic()
        for g in groups:
            try:
                tmin = min(g['pipeline_timestamp'])
                pid = g['pipeline_id']
                self.print('BeamGrouper: Elapsed Time for %i: %.3f sec (pipeline timestamp: %s)' %
                           (pid, tnow - tmin, tmin))
            except:
                pass
        
        common_kwargs = {
            "dead_beam_nos": dead_beam_nos,
            "beam_activity": beam_activity,
            "coh_dm_activity": coh_dm_activity,
            "dm_activity_lookback": list(self.dm_activity_lookback),
            "beam_activity_lookback": list(self.beam_activity_lookback),
            "incoh_dm_activity": incoh_dm_activity,
            "dm_std": coh_events.dm.std(),
            "avg_l1_grade": avg_l1_grade,
        }
        return [pickle.dumps((g, common_kwargs), 2) for g in groups]

    def _cluster(self, events):
        """ Performs event clustering via DBSCAN algorithm """
        # make a new (time, dm, x, y) array that will be scaled by thresholds
        tdmxy = np.empty((len(events), 4), np.float32)
        times = events.timestamp_utc - events.timestamp_utc.min()
        tdmxy[:, 0] = times.astype("int64") / 1e3
        tdmxy[:, 1] = events.dm
        tdmxy[:, 2] = events.beam_no // 1000  # x (RA-like) in beam grid
        tdmxy[:, 3] = events.beam_no % 1000  # y (DEC-like) in beam grid
        tdmxy /= self.thresholds

        tree = cKDTree(tdmxy)
        neighbors = tree.query_ball_tree(tree, r=1.0, p=np.infty)

        groups = {}
        visiting = []
        undiscovered = set(range(len(events)))
        while undiscovered:
            root = undiscovered.pop()
            visiting.append(root)
            while visiting:
                event = visiting.pop()
                groups.setdefault(root, []).append(event)
                for new in set(neighbors[event]).intersection(undiscovered):
                    undiscovered.remove(new)
                    visiting.append(new)

        return [events[g] for g in list(groups.values())]

    def _cluster_with_incoh(self, groups, incoh_events):
        """ Group incoherent beam events with existing coherent beam groups """
        ungrouped = np.ones(len(incoh_events), dtype=bool)
        for i, group in enumerate(groups):
            best = group[group.snr.argmax()]
            dts = incoh_events.timestamp_utc - best.timestamp_utc
            dts = dts.astype("int64") / 1e3
            ddms = incoh_events.dm - best.dm
            to_add = ((np.abs(dts) <= self.thresholds[0]) &
                      (np.abs(ddms) <= self.thresholds[1]))
            ungrouped[to_add] = False
            groups[i] = groups[i].append(incoh_events[to_add])
        return groups + [e.reshape(1,) for e in incoh_events[ungrouped]]
