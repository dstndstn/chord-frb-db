from chord_frb_grpc import frb_sifter_pb2_grpc
from chord_frb_grpc.frb_sifter_pb2 import ConfigReply, FrbEventsReply
import queue
from chord_frb_sifter.pipeline import setup, simple_create_pipeline
from chord_frb_sifter.pipeline import simple_process_events

class FrbSifter(frb_sifter_pb2_grpc.FrbSifterServicer):
    def __init__(self, injections):
        # SimpleQueue is thread-safe
        self.event_queue = queue.SimpleQueue()
        self.beam_snr_queue = queue.SimpleQueue()
        self.injections = injections
        self.xengine_config = None
        self.pirate_config = None
        self.dedisp_config = None
        self.grouper_config = None

    def CheckConfiguration(self, request, context):
        print('CheckConfiguration: context', context)
        print('  peer:', context.peer())
        conf = request.xengine_yaml
        print('Received Xengine YAML config: "%s"' % conf)
        ok = True
        if self.xengine_config is None:
            self.xengine_config = conf
        else:
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
        # Demand exact equality... what could go wrong
        return conf == self.xengine_config

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
        if len(request.coarsegrain_snr):
            self.beam_snr_queue.put((request.beam_set_id,
                                     request.coarsegrain_start_fpga_count,
                                     request.coarsegrain_end_fpga_count,
                                     request.coarsegrain_snr))

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
    while True:
        beam_snr = beam_snr_queue.get()
        print('beam_snr_handler: got', len(beam_snr))

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
