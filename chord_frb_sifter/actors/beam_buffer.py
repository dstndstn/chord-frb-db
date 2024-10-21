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
    """
    def __init__(self,
                 counts_per_chunk=4096*384,
                 **kwargs):
        super(BeamBuffer, self).__init__(**kwargs)
        self.pipe_id = 0
        self.counts_per_chunk = counts_per_chunk
        self.hoping_for = set((i // 256 * 1000 + i % 256 for i in range(1024)))
        self.waiting_for = set()
        self.reported = set()
        self.reported_twice = set()
        self.reported_thrice = set()

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
            return out_item
        except:
            self.logger.error(traceback.format_exc())
            raise

    def _attempt_perform_action(self, item):
        """ perform_action helper function """
        beam, fpga_start, data = item  # L1 message
        beam, fpga_start = int(beam), int(fpga_start)

        self.logger.debug("Received:%04i %i" % (beam, fpga_start))
        print('BeamBuffer: beam', beam, 'fpga', fpga_start, 'data len:', len(data))
        if data:
            #print('BeamBuffer: appending event', data, 'before: timestamp:',
            #      getattr(self.blob, 'timestamp', None))
            e = L1Event(data)
            tnow = time.monotonic()
            e = e.copy()
            n_e = len(e)
            e['pipeline_timestamp'][:] = tnow
            e['pipeline_id'][:] = self.pipe_id + np.arange(n_e)
            #for i in range(n_e):
            #    self.print('BeamBuffer: received event %i at %s' % (e['pipeline_id'][i], tnow))
            self.pipe_id += n_e
            self.blob = self.blob.append(e)

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
                print('Dumping events because all waiting-for beams have reported')
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
        return [(msgpack.packb(missing), dump.tostring())]
