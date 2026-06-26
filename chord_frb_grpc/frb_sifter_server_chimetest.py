"""
gRPC server for the CHIME testbed.

Receives fully-populated L1 events from N simulated search nodes,
collects events per chunk, and dispatches to the sifting pipeline.

Usage:
    CHORD_FRB_DB_URL=sqlite+pysqlite:///path/to/db.sqlite3 \\
        python frb_sifter_server.py --n-nodes 4 [--port 50051]
"""

import argparse
import threading
import numpy as np

from chord_frb_grpc import frb_sifter_chime_pb2_grpc
from chord_frb_grpc.frb_sifter_chime_pb2 import ConfigReply, FrbEventsReply

def _proto_event_to_l1(e, message):
    chunk_utc = message.frame0_nano / 1000. + message.chunk_fpga_count * 2.56
    return {
        'beam':                   e.beam_id,
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
    def __init__(self, pipeline, n_nodes, injections=False):
        self.pipeline = pipeline
        self.n_nodes = n_nodes
        self.injections = injections
        self.config = None
        self._lock = threading.Lock()
        # chunk_fpga_count → {'events': [...], 'beam_sets': set()}
        self._chunk_buffer = {}

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

        chunk = request.chunk_fpga_count
        beam_set = request.beam_set_id
        l1_events = [_proto_event_to_l1(e, request) for e in request.events]

        dispatch_events = None
        with self._lock:
            if chunk not in self._chunk_buffer:
                self._chunk_buffer[chunk] = {'events': [], 'beam_sets': set()}
            buf = self._chunk_buffer[chunk]
            buf['events'].extend(l1_events)
            buf['beam_sets'].add(beam_set)
            print('Chunk %d: node %d reported %d events (%d/%d nodes)'
                  % (chunk, beam_set, len(l1_events), len(buf['beam_sets']), self.n_nodes))
            if len(buf['beam_sets']) == self.n_nodes:
                dispatch_events = buf['events']
                del self._chunk_buffer[chunk]

        if dispatch_events is not None:
            self._dispatch(chunk, dispatch_events)

        return FrbEventsReply(ok=True, message='')

    def _dispatch(self, chunk, all_events):
        from chord_frb_sifter.chime_test_pipeline import process_events

        # group by beam
        beams = {}
        for ev in all_events:
            b = ev['beam']
            beams.setdefault(b, []).append(ev)

        stats = {'in': len(all_events), 'out': 0, 'rfi': 0, 'astro': 0, 'known': 0}
        for beam_events in beams.values():
            outputs = process_events(self.pipeline, beam_events)
            for ev in outputs:
                if not isinstance(ev, dict):
                    continue
                stats['out'] += 1
                if ev.get('is_rfi', False):
                    stats['rfi'] += 1
                else:
                    stats['astro'] += 1
                if ev.get('known_source_name', ''):
                    stats['known'] += 1

        print('Chunk %d dispatched: %d L1 in → %d L2 out (%d RFI, %d astro, %d known)'
              % (chunk, stats['in'], stats['out'], stats['rfi'], stats['astro'], stats['known']))


def serve(pipeline, n_nodes, port=50051, max_threads=10, injections=False):
    import grpc
    from concurrent import futures

    servicer = FrbSifterChime(pipeline, n_nodes=n_nodes, injections=injections)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_threads))
    frb_sifter_chime_pb2_grpc.add_FrbSifterChimeServicer_to_server(servicer, server)
    server.add_insecure_port('[::]:' + str(port))
    print('Server started on port %d, waiting for %d node(s)' % (port, n_nodes))
    server.start()
    return server, servicer


if __name__ == '__main__':
    import logging
    logging.basicConfig()

    parser = argparse.ArgumentParser(description='CHIME testbed gRPC sifter server')
    parser.add_argument('--n-nodes', type=int, default=4,
                        help='Number of search nodes to wait for per chunk')
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

    server, servicer = serve(pipeline, n_nodes=args.n_nodes, port=args.port)
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print('Shutting down...')
        server.stop(1)
        for _, actor in pipeline:
            actor.shutdown()
