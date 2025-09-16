from chord_frb_grpc import frb_sifter_pb2_grpc
from chord_frb_grpc.frb_sifter_pb2 import ConfigReply, FrbEventsReply
import queue


class FrbSifter(frb_sifter_pb2_grpc.FrbSifterServicer):
    def __init__(self, injections):
        # SimpleQueue is thread-safe
        self.message_queue = queue.SimpleQueue()
        self.injections = injections
        self.config = None

    def CheckConfiguration(self, request, context):
        conf = request.yaml
        print('CheckConfiguration: context', context)
        print('  peer:', context.peer())
        print('Received YAML config: "%s"' % conf)
        ok = True
        if self.config is None:
            self.config = conf
        else:
            if self.config == conf:
                pass
            else:
                print('YAML config mismatch!')
                ok = False
        r = ConfigReply(ok=ok)
        return r

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
        
        return FrbEventsReply(ok=ok, message=msg)

def serve(sifter, port=50051, max_threads=10):
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
    sifter = FrbSifter()
    server = serve(sifter)
    server.wait_for_termination()
