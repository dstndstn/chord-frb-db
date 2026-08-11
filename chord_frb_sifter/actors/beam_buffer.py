"""
This is a CHORD/FRB prototype version, modified from CHIME/FRB.
This actor buffers input from L1, gathering all events from a given time-chunk of data.
"""
import time
import traceback
from datetime import datetime

import numpy as np

from chord_frb_sifter.actors import Actor
from chord_frb_sifter.event import EventGroup

class BeamBuffer(Actor):
    """
    The purpose of this class is to accumulate events from individual beams
    into a single frame, such that events may be grouped.
    """
    def __init__(self, sifter=None, **kwargs):
        super().__init__(**kwargs)
        self.sifter = sifter
        self.pipe_id = 0

        self.current_chunk = None
        self.buffered_events = []

        self.current_beamsets = set()
        self.expecting_beamsets = None

    def __str__(self):
        return 'BeamBuffer'

    def _perform_action(self, event_group):
        # Assume the event_groups we get are from a single time-chunk and beamset.

        # We will group these into (one or more) event_groups each from a single time-chunk.

        # for debugging purposes, tag events...
        tnow = time.monotonic()
        for e in event_group.events:
            e['pipeline_timestamp'] = tnow
            e['pipeline_id'] = self.pipe_id
            self.pipe_id += 1

        # Return value - flushed event groups
        rtn = []

        def _flush():
            # Only send event-groups downstream if there are actually events!
            if not any([len(g.events)>0 for g in self.buffered_events]):
                return
            chunk_group = EventGroup(chunk_utc = self.current_chunk,
                                     events = [],
                                     n_beamsets = len(self.buffered_events),
                                     )
            chunk_group.n_live_beams = 0
            for g in self.buffered_events:
                chunk_group.events.extend(g.events)
                chunk_group.n_live_beams += len(self.sifter.beamset_to_beam_ids(g.beamset))
            rtn.append(chunk_group)

        # This is a "while True" loop because there's one case where we want to loop twice;
        # the normal case is to "break" out
        while True:
            if self.current_chunk is None:
                print('Starting to collect event_group for chunk %s' % event_group.chunk_utc)
                self.current_chunk = event_group.chunk_utc
    
            if event_group.chunk_utc == self.current_chunk:
                self.buffered_events.append(event_group)
                self.current_beamsets.add(event_group.beamset)
                if self.current_beamsets == self.expecting_beamsets:
                    # Received all beamsets - flush events!
                    print('Received all beamsets expected for chunk %s' % event_group.chunk_utc)
                    _flush()
                    self.buffered_events = []
                    self.current_chunk = None

            elif event_group.chunk_utc < self.current_chunk:
                # Slowpoke
                if len(event_group.events):
                    rtn.append(EventGroup(chunk_utc = event_group.chunk_utc,
                                          events = event_group.events))
                # we should expect this beamset next time
                self.current_beamsets.add(event_group.beamset)

            elif event_group.chunk_utc > self.current_chunk:
                # Got the first event_group of a new chunk.
                # If this is the first chunk, this is expected.  Otherwise, we expect to receive
                # all beamsets that we were expecting.  So this possibly indicates one beamset
                # running fast?
                if self.expecting_beamsets is None:
                    # If we're starting up -- next chunk, we expect the same beamsets
                    self.expecting_beamsets = self.current_beamsets
                    print('Received the first event_group for the next chunk')
                else:
                    print('Received an unexpected event_group for chunk %s while processing chunk %s' %
                          (event_group.chunk_utc, self.current_chunk))
                # Flush the current_chunk
                _flush()
                # Set my state ready for this first event_group in the next chunk & repeat the loop
                self.buffered_events = []
                self.current_chunk = None
                continue

            # Normal case - one time through the loop
            break

        return rtn


    # # First, group events into per-time-chunk, per-beam event groups.  This makes life easier below.
        # beam_groups = []
        # current_group = None
        # for e in events:
        #     if current_group is not None and e.beam_id != current_group.beam_id:
        #         beam_groups.append(current_group)
        #         current_group = None
        #     if current_group is None:
        #         current_group = EventGroup(chunk_utc = event_group.chunk_utc,
        #                                    beamset = event_group.beamset,
        #                                    beam_id = e.beam_id,
        #                                    events = [])
        #     current_group.events.append(e)
        # if current_group is not None:
        #     beam_groups.append(current_group)


        # rtn = []
        # def _flush_events():
        #     if len(self.slowpoke_events):
        #         print('Flushing', len(self.slowpoke_events), 'slow-pokes')
        #         rtn.append(self.slowpoke_events)
        #         self.slowpoke_events = []
        #     if len(self.buffered_events):
        #         print('Flushing', len(self.buffered_events), 'events')
        #         rtn.append(self.buffered_events)
        #         self.buffered_events = []
        #     self.expecting_beams = self.current_beams
        #     self.current_beams = set()
        #     self.previous_chunk = self.current_chunk
        # 
        # def _append_events(lst, evts):
        #     for e in evts:
        #         #if not e.get('null_event', False):
        #         #    lst.append(e)
        #         lst.append(e)
        # 
        # for chunk, beam, events in event_sets:
        #     if chunk == self.previous_chunk:
        #         # slowpoke -- at startup, or when replaying from a file, you could get:
        #         #  chunk 0, beam 1
        #         #
        #         #  chunk 1, beam 2
        #         #  chunk 1, beam 1 --> flush!
        #         #  chunk 1, beam 3 --> slowpoke!
        #         #
        #         #  chunk 2, beam 2
        #         #  chunk 2, beam 3
        #         #  chunk 2, beam 1 --> flush!
        #         #
        #         #  etc.
        #         self.expecting_beams.add(beam)
        #         # FIXME -- append to previous event set?
        #         print('Got slow-poke event: chunk', chunk, 'current', self.current_chunk,
        #               'previous', self.previous_chunk, 'beam:', beam)
        #         if len(rtn):
        #             print('adding to last batch')
        #             _append_events(rtn[-1], events)
        #         else:
        #             print('adding to slow-pokes')
        #             _append_events(self.slowpoke_events, events)
        #         continue
        # 
        #     if self.current_chunk is None:
        #         self.current_chunk = chunk
        #         print('Starting new batch: chunk', chunk, 'expecting beams:', self.expecting_beams)
        #         if len(self.slowpoke_events):
        #             print('Flushing', len(self.slowpoke_events), 'slow-pokes')
        #             rtn.append(self.slowpoke_events)
        #             self.slowpoke_events = []
        # 
        #     if chunk > self.current_chunk:
        #         # We got the first event from a new chunk -- flush our current event list!
        #         print('New chunk - flushing %i events for chunk %s; beams %s' %
        #               (len(self.buffered_events), self.current_chunk, self.current_beams))
        #         _flush_events()
        #         self.current_chunk = chunk
        # 
        #     if chunk < self.current_chunk:
        #         # FIXME -- very slow event... do something??
        #         print('Ignoring old events: chunk', chunk, 'but current is', self.current_chunk,
        #               'and previous was', self.previous_chunk, '; events are', events)
        #         continue
        # 
        #     self.current_beams.add(beam)
        #     _append_events(self.buffered_events, events)
        # 
        #     if self.expecting_beams is not None:
        #         if self.current_beams.issuperset(self.expecting_beams):
        #             # All expected beams have been received -- flush our current event list!
        #             print('Got all beams (%s) - expected beams (%s) - flushing %i events for chunk %s' %
        #                   (self.current_beams, self.expecting_beams, len(self.buffered_events), self.current_chunk))
        #             _flush_events()
        #             self.current_chunk = None
        #             print('Next chunk, will expect beams %s' % self.expecting_beams)
        # 
        # return rtn
