"""
gRPC server for the CHIME testbed.

Receives fully-populated L1 events from N simulated search nodes and
dispatches them to the sifting pipeline via a queue. N-node aggregation
is handled by the BeamBuffer actor rather than the server.

Usage:
    CHORD_FRB_DB_URL=sqlite+pysqlite:///path/to/db.sqlite3 \\
        python frb_sifter_server_chimetest.py [--port 50051]
"""

import argparse
import queue
import threading
import numpy as np

from chord_frb_grpc import frb_sifter_chime_pb2_grpc
from chord_frb_grpc.frb_sifter_chime_pb2 import ConfigReply, FrbEventsReply

def _proto_event_to_l1(e, message):
    chunk_utc = message.frame0_nano / 1000. + message.chunk_fpga_count * 2.56
    return {
        'beam_id':                e.beam_id,
        'timestamp_fpga':         e.fpga_timestamp,
        'timestamp_utc':          e.timestamp_utc,
        'chunk_fpga':             message.chunk_fpga_count,
        'chunk_utc':              chunk_utc,
        'dm':                     e.dm,
        'snr':                    e.snr,
        'tree_index':             e.tree_index,
        'snr_scale':              e.snr_scale,
        'spectral_index':         e.spectral_index,
        'scattering_measure':     e.scattering_measure,
        'level1_nhits':           e.level1_nhits,
        'rfi_grade_level1':       e.rfi_grade_level1,
        'rfi_mask_fraction':      e.rfi_mask_fraction,
        'rfi_clip_fraction':      e.rfi_clip_fraction,
        'snr_vs_dm':              np.array(e.snr_vs_dm, dtype=np.float32),
        'snr_vs_tree_index':      np.array(e.snr_vs_tree_index, dtype=np.float32),
        'snr_vs_spectral_index':  np.array(e.snr_vs_spectral_index, dtype=np.float32),
        'beam_dra':               e.beam_dra,
        'beam_ddec':              e.beam_ddec,
        'beam_grid_x':            e.beam_grid_x,
        'beam_grid_y':            e.beam_grid_y,
        'is_incoherent':          e.is_incoherent,
    }


class FrbSifterChime(frb_sifter_chime_pb2_grpc.FrbSifterChimeServicer):
    def __init__(self, pipeline, injections=False):
        self.pipeline = pipeline
        self.injections = injections
        self.config = None
        self._lock = threading.Lock()
        self.event_queue = queue.SimpleQueue()

    def CheckConfiguration(self, request, context):
        conf = request.yaml
        print('CheckConfiguration from %s' % context.peer())
        ok = True
        with self._lock:
            if self.config is None:
                self.config = conf
                print('  Config accepted (first node)')
            elif self.config == conf:
                print('  Config matches')
            else:
                print('  Config MISMATCH — rejecting node')
                ok = False
        return ConfigReply(ok=ok)

    def FrbEvents(self, request, context):
        if request.has_injections != self.injections:
            msg = ('Expected has_injections=%s, got %s'
                   % (self.injections, request.has_injections))
            return FrbEventsReply(ok=False, message=msg)

        l1_events = [_proto_event_to_l1(e, request) for e in request.events]
        print('Chunk %d beam-set %d: %d events'
              % (request.chunk_fpga_count, request.beam_set_id, len(l1_events)))
        if l1_events:
            self.event_queue.put(l1_events)
        return FrbEventsReply(ok=True, message='')


def event_handler(event_queue, pipeline):
    from chord_frb_sifter.chime_test_pipeline import process_events
    while True:
        l1_events = event_queue.get()
        process_events(pipeline, l1_events)


def serve(pipeline, port=50051, max_threads=10, injections=False):
    import grpc
    from concurrent import futures

    servicer = FrbSifterChime(pipeline, injections=injections)

    t = threading.Thread(target=event_handler,
                         args=(servicer.event_queue, pipeline), daemon=True)
    t.start()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_threads))
    frb_sifter_chime_pb2_grpc.add_FrbSifterChimeServicer_to_server(servicer, server)
    server.add_insecure_port('[::]:' + str(port))
    print('Server started on port %d' % port)
    server.start()
    return server, servicer


if __name__ == '__main__':
    import logging
    logging.basicConfig()

    parser = argparse.ArgumentParser(description='CHIME testbed gRPC sifter server')
    parser.add_argument('--port', type=int, default=50051)
    parser.add_argument('--db-url', default=None,
                        help='SQLAlchemy DB URL (overrides CHORD_FRB_DB_URL env var)')
    args = parser.parse_args()

    if args.db_url:
        import os
        os.environ['CHORD_FRB_DB_URL'] = args.db_url

    from chord_frb_sifter.chime_test_pipeline import setup, create_pipeline
    setup()
    pipeline = create_pipeline()

    server, servicer = serve(pipeline, port=args.port)
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print('Shutting down...')
        server.stop(1)
        for _, actor in pipeline:
            actor.shutdown()
