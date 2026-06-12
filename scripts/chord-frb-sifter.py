from chord_frb_grpc import frb_sifter_pb2_grpc
from chord_frb_grpc.frb_sifter_pb2 import ConfigReply, FrbEventsReply
import queue
from chord_frb_sifter.pipeline import setup, simple_create_pipeline
from chord_frb_sifter.pipeline import simple_process_events

import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
from datetime import datetime

'''
This script opens a gRPC server socket listening for connections from Pirate.
It loads the pipeline and sends any events it receives through the pipeline.
'''

class FrbSifter(frb_sifter_pb2_grpc.FrbSifterServicer):
    def __init__(self, injections):
        # SimpleQueue is thread-safe
        self.event_queue = queue.SimpleQueue()
        self.beam_snr_queue = queue.SimpleQueue()
        self.injections = injections
        self.xengine_config_yaml = None
        self.xengine_config = None
        self.pirate_config = None
        self.dedisp_config = None
        self.grouper_config = None

        # beamset (int) -> arrays of (id, x, y)
        self.beamset_meta = {}

    def CheckConfiguration(self, request, context):
        print('CheckConfiguration: context', context)
        print('  peer:', context.peer())
        conf = request.xengine_yaml
        print('Received Xengine YAML config: "%s"' % conf)
        ok = True
        if not self.check_xengine_config(conf):
            print('YAML config mismatch (Xengine)!')
            ok = False
        conf = request.pirate_yaml
        print('Received Pirate YAML config: "%s"' % conf)
        if self.pirate_config is None:
            self.pirate_config = conf
        else:
            if not self.check_pirate_config(conf):
                print('YAML config mismatch (Pirate)!')
                ok = False
        conf = request.dedispersion_plan_yaml
        print('Received Pirate dedisperser YAML config: "%s"' % conf)
        if self.dedisp_config is None:
            self.dedisp_config = conf
        else:
            if not self.check_dedisp_config(conf):
                print('YAML config mismatch (Dedisp)!')
                ok = False
        conf = request.grouper_yaml
        print('Received Pirate Grouper YAML config: "%s"' % conf)
        if self.grouper_config is None:
            self.grouper_config = conf
        else:
            if not self.check_grouper_config(conf):
                print('YAML config mismatch (Grouper)!')
                ok = False
        r = ConfigReply(ok=ok)
        return r

    def check_xengine_config(self, conf):
        if self.xengine_config_yaml is None:
            self.xengine_config_yaml = conf
            # Parse it...
            self.xengine_config = yaml.load(self.xengine_config_yaml, Loader=Loader)

            conf = self.xengine_config
            beamset = conf['beamset']
            if beamset in self.beamset_meta:
                print('Already received beamset %i' % beamset)
                return False
            self.beamset[beamset] = (conf['beam_ids'],
                                     conf['beam_positions_x'],
                                     conf['beam_positions_y'])

        else:
            # Demand exact equality... what could go wrong
            return conf == self.xengine_config_yaml
        return True

    def check_pirate_config(self, conf):
        # Demand exact equality... what could go wrong
        return conf == self.pirate_config

    def check_dedisp_config(self, conf):
        # Demand exact equality... what could go wrong
        return conf == self.dedisp_config
    
    def check_grouper_config(self, conf):
        # Demand exact equality... what could go wrong
        return conf == self.grouper_config

    def FrbEvents(self, request, context):
        print('FRB Events')
        if request.has_injections != self.injections:
            print('Received FRB Events %s injections, but this FRB Sifter is%s handling injections!' % ('with' if request.has_injections else 'without', '' if self.injections else ' not'))
            return FrbEventsReply(ok=False, message='Expected has_injections=%s, got %s - are you sending to the wrong FRB Sifter (injection vs prod)?' % (self.injections, request.has_injections))
        msg = ''
        ok = True

        print('beam-set', request.beam_set_id, 'chunk FPGA', request.chunk_fpga_count, 'with', len(request.events), 'events')
        for e in request.events:
            print('  event', e)
        if len(request.events):
            self.event_queue.put(request.events)

        print('Coarse-grained array FPGA-count start & stop',
              request.coarsegrain_start_fpga_count,
              request.coarsegrain_end_fpga_count)
        print('Coarse-grained array length:', len(request.coarsegrain_snr))
        print('Peer:', context.peer())
        if len(request.coarsegrain_snr):
            self.beam_snr_queue.put(dict(beamset=request.beam_set_id,
                                         fpga_start=request.coarsegrain_start_fpga_count,
                                         fpga_end=request.coarsegrain_end_fpga_count,
                                         beam_snr=request.coarsegrain_snr,
                                         peer=context.peer()))

        return FrbEventsReply(ok=ok, message=msg)

def serve(sifter, port=10000, max_threads=10):
    import grpc
    from concurrent import futures
    #from chord_frb_grpc import frb_sifter_pb2_grpc

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_threads))

    frb_sifter_pb2_grpc.add_FrbSifterServicer_to_server(sifter, server)

    server.add_insecure_port('[::]:' + str(port))
    print('Server started, listening on', port)
    server.start()
    return server

def event_handler(sifter, event_queue, pipeline):
    while True:
        events = event_queue.get()
        print('event_handler: got', len(events), 'events')
        simple_process_events(pipeline, events)

def beam_snr_handler(sifter, beam_snr_queue, database):
    known_beamsets = set()
    while True:
        beam_snr = beam_snr_queue.get()
        #print('beam_snr_handler: got', len(beam_snr))
        #beamset, fpga_start, fpga_end, snr_array = beam_snr
        beamset = beam_snr['beamset']
        fpga_start = beam_snr['fpga_start']
        fpga_end = beam_snr['fpga_end']
        peer = beam_snr['peer']
        snr_array = beam_snr['beam_snr']
        if beamset not in known_beamsets:
            # Add a database entry describing this beamset: beam ids, x,y locations,
            # peer?, unix_nano0, date of first message?
            print('Looking up beamset', beamset, 'in xengine YAML...')
            print(sifter.xengine_config)

            if not beamset in sifter.beamset_meta:
                print('Unknown beamset', beamset)
                continue

            beam_ids, beam_x, beam_y = sifter.beamset_meta[beamset]

            # Add beamset, beam_ids, beam_x, beam_y to the db!
            known_beamsets.add(beamset)

            # timing ... this only needs to get initialized once!
            xengine = sifter.xengine_config
            seq_per_frb_time_sample = xengine['seq_per_frb_time_sample']
            fpga0_nano = xengine['unix_ns_at_seq_0']
            nano_per_fpga = xengine['dt_ns_per_seq']
            print('FPGA seq per time sample:', seq_per_frb_time_sample)
            print('nanoseconds per FPGA seq:', nano_per_fpga)

        unix_time_nano_start = fpga0_nano + fpga_start * nano_per_fpga
        unix_time_nano_end   = fpga0_nano + fpga_end   * nano_per_fpga
        nano = 1_000_000_000
        date_start = datetime.fromtimestamp(unix_time_nano_start // nano +
                                            1e-9 * (unix_time_nano_start % nano))
        date_end = datetime.fromtimestamp(unix_time_nano_end // nano +
                                          1e-9 * (unix_time_nano_end % nano))

        # Add beamset, date_start, date_end, snr_array to the db!

'''
Example xengine metadata:

beamset: 0
beam_ids: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
beam_positions_x: [-0.10000000000000001, -0.03333333333333334, 0.033333333333333326, 0.10000000000000001, -0.10000000000000001, -0.03333333333333334, 0.033333333333333326, 0.10000000000000001, -0.10000000000000001, -0.03333333333333334, 0.033333333333333326, 0.10000000000000001, -0.10000000000000001, -0.03333333333333334, 0.033333333333333326, 0.10000000000000001]
beam_positions_y: [-0.10000000000000001, -0.10000000000000001, -0.10000000000000001, -0.10000000000000001, -0.03333333333333334, -0.03333333333333334, -0.03333333333333334, -0.03333333333333334, 0.033333333333333326, 0.033333333333333326, 0.033333333333333326, 0.033333333333333326, 0.10000000000000001, 0.10000000000000001, 0.10000000000000001, 0.10000000000000001]
unix_ns_at_seq_0: 1772483060000000000
dt_ns_per_seq: 5120
seq_per_frb_time_sample: 195
tel_origin_itrs_lat_deg: 49.320751444439999
tel_origin_itrs_lon_deg: -119.62081125
tel_grid_x_axis: [0.99997434239835936, -3.7539331442771999e-05, -0.0071633187676754936]
tel_grid_y_axis: [6.5403387739209999e-05, 0.99999243322034881, 0.0038896303735576139]
tel_dish_elev_axis: [0.99999999838132392, -5.6897733584326999e-05, 0]
tel_dish_vert_axis: [0, 0, 1]
tel_dish_coelev_deg: 0
tel_dish_separation_x_m: 6.300156854906823
tel_dish_separation_y_m: 8.5000578097963082
'''

def main():
    import threading
    from chord_frb_db.utils import get_db_engine
    #from chord_frb_sifter.pipeline import setup, simple_create_pipeline
    #from chord_frb_sifter.pipeline import simple_process_events

    is_injections = False
    sifter = FrbSifter(is_injections)

    database_engine = get_db_engine()

    # Load pipeline config file
    setup()

    pipeline = simple_create_pipeline(database_engine)

    event_thread = threading.Thread(target=event_handler,
                                    args=(sifter, sifter.event_queue, pipeline),
                                    name='event-handler')
    event_thread.start()

    beam_snr_thread = threading.Thread(target=beam_snr_handler,
                                       args=(sifter, sifter.beam_snr_queue, database_engine),
                                       name='beam-snr-handler')
    beam_snr_thread.start()

    server = serve(sifter)
    server.wait_for_termination()

if __name__ == '__main__':
    import logging
    logging.basicConfig()
    main()
