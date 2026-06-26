from chord_frb_grpc import frb_sifter_pb2_grpc
from chord_frb_grpc.frb_sifter_pb2 import ConfigReply, FrbEventsReply
import queue


class FrbSifter(frb_sifter_pb2_grpc.FrbSifterServicer):
    def __init__(self, injections):
        # SimpleQueue is thread-safe
        self.message_queue = queue.SimpleQueue()
        self.injections = injections
        self.xengine_config = None
        self.pirate_config = None

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
        r = ConfigReply(ok=ok)
        return r

    def check_xengine_config(self, conf):
        # Demand exact equality... what could go wrong
        return conf == self.xengine_config

    def check_pirate_config(self, conf):
        # Demand exact equality... what could go wrong
        return conf == self.pirate_config

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

        print('Coarse-grained array FPGA-count start & stop',
              request.coarsegrain_start_fpga_count,
              request.coarsegrain_end_fpga_count)
        print('Coarse-grained array length:', len(request.coarsegrain_snr))
            
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

if __name__ == '__main__':
    import logging
    logging.basicConfig()
    is_injections = False
    sifter = FrbSifter(is_injections)
    server = serve(sifter)
    server.wait_for_termination()
