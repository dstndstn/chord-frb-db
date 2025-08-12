# Copyright 2015 gRPC authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
"""The Python implementation of the GRPC helloworld.Greeter server."""
# from gprc:examples/python/helloworld

from concurrent import futures
import logging

import grpc
import helloworld_pb2
import helloworld_pb2_grpc

import time
#import threading
#qlock = threading.Lock()
#msgqueue = 

import queue
# SimpleQueue is thread-safe
message_queue = queue.SimpleQueue()

class Greeter(helloworld_pb2_grpc.GreeterServicer):
    def SayHello(self, request, context):
        global message_queue
        message_queue.put(request.name)
        return helloworld_pb2.HelloReply(message="Hello, %s!" % request.name)

def pipeline_loop():
    global message_queue
    while True:
        print('Queue has (approximately) %i messages waiting' % (message_queue.qsize()))
        try:
            message = message_queue.get(timeout=5.)
        except queue.Empty:
            # No messages waiting; timed out.
            # do something while idling...?
            continue

        print('Dequeued message', message)
        # process it...
        time.sleep(0.01)



        
def serve():
    port = "50051"
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    helloworld_pb2_grpc.add_GreeterServicer_to_server(Greeter(), server)
    server.add_insecure_port("[::]:" + port)
    server.start()
    print("Server started, listening on " + port)
    pipeline_loop()
    server.wait_for_termination()

if __name__ == "__main__":
    logging.basicConfig()
    serve()
