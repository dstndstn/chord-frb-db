"""
This is a CHORD/FRB prototype version, modified from CHIME/FRB.
This module contains the class that buffers input from L1 """

from os import path
import traceback
from datetime import datetime

import numpy as np
import msgpack

import time

from frb_common import ActorBaseClass
from frb_common.events import L1Event

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

        self.processing_fpga = None
        self.buffered_events = []

        # self.hoping_for = set((i // 256 * 1000 + i % 256 for i in range(1024)))
        # self.waiting_for = set()
        # self.reported = set()
        # self.reported_twice = set()
        # self.reported_thrice = set()

    def perform_action(self, item):
        """Method that performs the buffering (see class doc for more info).

        Parameters
        ----------
        item : list of events

        Returns
        -------
        None or [list of events]
            None if there is no completed frame ready to be dumped.  Otherwise,
            all the events from that frame.
        """
        try:
            out_item = self._attempt_perform_action(item)
            return out_item
        except:
            self.logger.error(traceback.format_exc())
            raise

    def _attempt_perform_action(self, events):
        """ perform_action helper function """
        if len(events) == 0:
            return None
        # ASSUME that we are given events for a single chunk of data and beam number.
        event = events[0]
        fpga_chunk = event['fpga_chunk']
        beam = event['beam_no']
        print('BeamBuffer: beam', beam, 'fpga', fpga_chunk)

        output = None

        if self.processing_fpga is None:
            # First event
            self.processing_fpga = fpga_chunk
        else:
            if fpga_chunk != self.processing_fpga:
                print('Dumping buffered events for FPGA', self.processing_fpga)
                output = self.buffered_events
                self.buffered_events = []
                self.processing_fpga = fpga_chunk

        tnow = time.monotonic()
        for e in events:
            # for debugging purposes, tag events...
            e['pipeline_timestamp'] = tnow
            e['pipeline_id'] = self.pipe_id
            self.pipe_id += 1
            self.buffered_events.append(e)

        return output
