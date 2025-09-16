from chord_frb_grpc import frb_sifter_pb2_grpc
from chord_frb_grpc.frb_sifter_pb2 import ConfigReply, FrbEventsReply
import queue


class FrbSifter(frb_sifter_pb2_grpc.FrbSifterServicer):
    def __init__(self):
        # SimpleQueue is thread-safe
        self.message_queue = queue.SimpleQueue()
        self.config = None

    def CheckConfiguration(self, request, context):
        conf = request.yaml
        print('Received YAML config: "%s"' % conf)
        ok = False
        if self.config is None:
            self.config = conf
            ok = True
        else:
            if self.config == conf:
                ok = True
            else:
                print('YAML config mismatch!')
                ok = False
        r = ConfigReply(ok=ok)
        return r
    

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
