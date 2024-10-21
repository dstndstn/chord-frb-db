# -*- coding: utf-8 -*-

""" This module contains the class that buffers input from L1 """

from os import path
import traceback
from datetime import datetime

import numpy as np
import msgpack

import time

from frb_common import ActorBaseClass
from frb_common.events import L1Event

__author__ = "CHIME FRB Group"
__version__ = "0.4"
__maintainer__ = "Alex Josephy"
__developers__ = "Alex Josephy"
__email__ = "alexander.josephy@mail.mcgill.ca"
__status__ = "Epsilon"


class BeamBuffer(ActorBaseClass):
    """
    The purpose of this class is to accumulate events from individual beams
    into a single frame, such that events may be grouped.

    Parameters
    ----------
    counts_per_chunk : int
        FPGA counts per L1 chunk, default is 4096*384
    heartbeat_url : string, optional
        frb-master endpoint to send the L2/L3 heartbeat to.
        Use `None` to disable.
    beam_status_url : string, optional
        frb-master endpoint to send updates on alive/dead status of L1 beams
        Use `None` to disable.
    exposure_dir : string, optional
        Directory to save/load daily exposure arrays. These arrays have full
        beam resolution (1024) and a 10-second time resolution (8640 bins).
        Use `None` to disable.
    **kwargs : dict, optional
        Additional parameters are used to initialize superclass
        (``ActorBaseClass``).

    Notes
    -----
    Since this actor takes input from L1 nodes, the events in the message
    packets are serialized via ``numpy`` rather than ``pickle`` to reduce the
    size. Because of this, if the ``BeamBuffer`` is the actor for a
    ``WorkerProcess`` object, its `use_pickle` parameter should be set to
    `False`.


    See Also
    --------
    frb_L2_L3.BeamGrouper :
        The downstream actor :ref:`(link) <L2_grouping_doc_page>`

    frb_common.ActorBaseClass :
        The superclass :ref:`(link) <actor_base_class_doc_page>`

    frb_common.WorkerProcess :
        The usual wrapping class :ref:`(link) <pipeline_tools_doc_page>`

    """

    def __init__(self, counts_per_chunk=4096*384,
                 heartbeat_url=None,
                 beam_status_url=None,
                 exposure_dir="./exposure", **kwargs):
        super(BeamBuffer, self).__init__(**kwargs)
        self.pipe_id = 0
        self.blob = L1Event("")
        self.counts_per_chunk = counts_per_chunk
        self.hoping_for = set((i // 256 * 1000 + i % 256 for i in range(1024)))
        self.waiting_for = set()
        self.reported = set()
        self.reported_twice = set()
        self.reported_thrice = set()

        self.utc_date = datetime.utcnow().date()
        self.exposure_dir = exposure_dir
        self.load_exposure()
        self.start_time = self.cur_time
        self.beam_status_url = beam_status_url
        if beam_status_url:
            metrics = {"{:04}".format(b):0 for b in self.hoping_for}
            payload = {"category":"deadbeams", "metrics":metrics}
            self.perform_post(self.beam_status_url, payload)
            self.heartbeat = {"category":"heartbeats", "metrics":{"L2L3":1}}
            self.perform_post(self.beam_status_url, self.heartbeat)

    @property
    def cur_time(self):
        """ String representation of current time to second precision """
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")

    def load_exposure(self):
        """ Attempts to load exposure array, starts fresh one on failure """
        try:
            exp_path = path.join(
                    self.exposure_dir,
                    self.utc_date.strftime("exposure_%y%m%d.npz"))
            self.exposure = np.load(exp_path)['exposure']
        except (IOError, TypeError):
            self.exposure = np.zeros((1024, 24*60*60//10), dtype=bool)
        return

    def save_exposure(self):
        """ If directory was specified, saves exposure array as npz file """
        try:
            if self.exposure_dir is None:
                return
            fn = self.utc_date.strftime("exposure_%y%m%d.npz")
            np.savez(path.join(self.exposure_dir, fn), exposure=self.exposure)
        except Exception as e:
            print ("file not found")
        return

    def mark_exposure(self):
        """
        Main exposure function. Gets current time bin (10 sec. resolution)
        and updates status of all reported beams to "exposed" (True). Note that
        the current UTC time is used, which will be slightly offset from the
        data time due to system latency.
        """
        now = datetime.utcnow()  # for simplicity

        # save and reset when date rolls over
        if now.date() != self.utc_date:
            self.save_exposure()
            self.utc_date = now.date()
            self.exposure_grid[:] = False

        # time bin is determined from seconds since midnight
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tidx = int((now - midnight).total_seconds() // 10)

        # mark exposure for beams that have reported
        beams = np.array(list(self.reported))
        self.exposure[(beams // 1000) * 256 + beams % 1000, tidx] = True
        return

    def perform_action(self, item):
        """Method that performs the buffering (see class doc for more info).

        Parameters
        ----------
        item : list of str
            Elements are as follows: `item` [0] is the beam id. `item` [1] is
            the time-step. `item` [2] is the result of
            ``str(numpy.ndarray.dtype.descr)`` call, and `item` [2] is the
            result of a ``numpy.ndarray.tostring()`` call.

        Returns
        -------
        None or [list of str]
            None if there is no completed frame ready to be dumped.  Otherwise,
            the first element of the list is a serialized list of any missing
            beams (generated via ``msgpack.packb``), the second element is the
            result of ``str(numpy.ndarray.dtype.descr)``, and the third element
            is the result of a ``numpy.ndarray.tostring()`` call- where the
            array in question contains all L1 events within the completed frame.

        """
        try:
            out_item = self._attempt_perform_action(item)
            if out_item is not None:
                self.PROCESS_STATUS.labels(
                    status="success", actor=self.process_name
                ).inc()
            return out_item
        except:
            self.PROCESS_STATUS.labels(status="failure", actor=self.process_name).inc()
            self.logger.error(traceback.format_exc())
            raise

    def _attempt_perform_action(self, item):
        """ perform_action helper function """
        beam, fpga_start, data = item  # L1 message
        beam, fpga_start = int(beam), int(fpga_start)

        self.logger.debug("Received:%04i %i" % (beam, fpga_start))

        if fpga_start < self.counts_per_chunk:  # got chunk index rather than fpga count
            fpga_start *= self.counts_per_chunk

        print('BeamBuffer: beam', beam, 'fpga', fpga_start, 'data len:', len(data))
        if data:
            #print('BeamBuffer: appending event', data, 'before: timestamp:',
            #      getattr(self.blob, 'timestamp', None))
            e = L1Event(data)
            tnow = time.monotonic()
            #self.print('BeamBuffer: created new event', type(e), e, 'setting time', tnow)
            e = e.copy()
            #print('e copy:', type(e))
            n_e = len(e)
            e['pipeline_timestamp'][:] = tnow
            e['pipeline_id'][:] = self.pipe_id + np.arange(n_e)
            #for i in range(n_e):
            #    self.print('BeamBuffer: received event %i at %s' % (e['pipeline_id'][i], tnow))
            self.pipe_id += n_e
            self.blob = self.blob.append(e)

            #self.blob = self.blob.append(L1Event(data))

            #print('BeamBuffer: appending event', data, 'after: timestamp:',
            #      getattr(self.blob, 'timestamp', None))
        if beam not in self.hoping_for:
            print('Beam not in hoping_for')
            return
        elif beam not in self.waiting_for:
            print('Beam not in waiting_for')
            self.waiting_for.add(beam)
        elif beam not in self.reported:
            print('Beam not in reported')
            self.reported.add(beam)
            if self.reported.issuperset(self.waiting_for):
                print('Dumping events')
                return self._dump_events(fpga_start + self.counts_per_chunk)
        elif beam not in self.reported_twice:
            print('Beam not in reported_twice')
            self.reported_twice.add(beam)
        elif beam not in self.reported_thrice:
            print('Beam not in reported_thrice')
            self.reported_thrice.add(beam)
        else:
            print('Beam lost')
            lost = self.waiting_for.difference(self.reported)
            if len(lost) > 0:
                self.logger.warning("Lost %i beams!" % len(lost))
            print('Dumping events')
            out = self._dump_events(fpga_start)
            self.reported.add(beam)
            return out

    def _dump_events(self, cutoff):
        self.mark_exposure()
        self.logger.debug("Dumping:%i" % cutoff)

        missing = list(self.hoping_for.difference(self.reported))
        if self.beam_status_url:
            beam_status = {"{:04}".format(b):0 for b in missing}
            received = self.hoping_for.intersection(self.reported)
            beam_status.update({"{:04}".format(b):1 for b in received})
            payload = {"category":"deadbeams", "metrics":beam_status}
            self.perform_patch(self.beam_status_url, payload)
            self.perform_patch(self.beam_status_url, self.heartbeat)

        self.waiting_for = self.reported
        self.reported = set()
        self.reported_twice = set()
        self.reported_thrice = set()
        dump = self.blob[self.blob.timestamp_fpga < cutoff]
        if len(dump) is 0:
            return None

        tnow = time.monotonic()
        pids = dump['pipeline_id']
        ts = dump['pipeline_timestamp']
        for i in range(len(dump)):
            self.print('BeamBuffer: dumping event %i, Elapsed Time %.3f' % (pids[i], tnow-ts[i]))

        self.blob = self.blob[self.blob.timestamp_fpga >= cutoff]
        #print('Dumping', len(dump), 'events', type(dump), type(dump[0]))
        #      'timestamp:', getattr(self.blob, 'timestamp', None))
        return [(msgpack.packb(missing), dump.tostring())]

    def update(self):
        self.save_exposure()

    def shutdown(self):
        self.save_exposure()
        self.logger.info("I have shutdown gracefully")
