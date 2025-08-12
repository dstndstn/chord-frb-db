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
import random

import threading
#qlock = threading.Lock()
#msgqueue = 

import queue
# SimpleQueue is thread-safe
message_queue = queue.SimpleQueue()
db_action_queue = queue.SimpleQueue()
# maybe we want high-priority callbacks?
#   maxsize=int
intensity_callback_queue = queue.PriorityQueue()
baseband_callback_queue = queue.PriorityQueue()

# the queue.PriorityQueue docs suggest doing this for priority queue data items.
from dataclasses import dataclass, field
from typing import Any
@dataclass(order=True)
class PrioritizedItem:
    priority: int
    item: Any=field(compare=False)

# This is the server side of the gRPC call.
class Greeter(helloworld_pb2_grpc.GreeterServicer):
    def SayHello(self, request, context):
        global message_queue
        message_queue.put(request.name)
        return helloworld_pb2.HelloReply(message="Hello, %s!" % request.name)

def pipeline_loop():
    global message_queue
    global db_action_queue
    global intensity_callback_queue

    while True:
        print('Message queue has (approximately) %i messages waiting' % (message_queue.qsize()))
        try:
            message = message_queue.get(timeout=5.)
        except queue.Empty:
            # No messages waiting; timed out.
            # do something while idling...?
            continue

        print('Dequeued message', message)
        # process it...
        time.sleep(0.01)
        # do actions on some events
        if message[-1] == '3':
            db_action_queue.put('db-'+message)
            priority = random.randint(0, 100)
            intensity_callback_queue.put(PrioritizedItem(priority=priority,
                                                         item='int-'+message))

def db_loop():
    global db_action_queue
    while True:
        print('DB queue has (approximately) %i messages waiting' %
              (db_action_queue.qsize()))
        try:
            action = db_action_queue.get(timeout=5.)
        except queue.Empty:
            # No messages waiting; timed out.
            # do something while idling...?
            continue
        print('Dequeued DB action', action)
        # process it...
        time.sleep(0.5)
    
def intensity_callback_loop():
    global intensity_callback_queue
    while True:
        print('Intensity callback queue has (approximately) %i messages waiting' %
              (intensity_callback_queue.qsize()))
        try:
            cb = intensity_callback_queue.get(timeout=5.)
        except queue.Empty:
            # No messages waiting; timed out.
            # do something while idling...?
            continue
        print('Dequeued intensity callback', cb)
        # process it...
        time.sleep(0.5)
        
def serve():
    port = "50051"
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    helloworld_pb2_grpc.add_GreeterServicer_to_server(Greeter(), server)
    server.add_insecure_port("[::]:" + port)
    server.start()
    print("Server started, listening on " + port)

    db_thread = threading.Thread(target=db_loop, name='db-action')
    db_thread.start()
    intensity_thread = threading.Thread(target=intensity_callback_loop,
                                        name='intensity-callbac')
    intensity_thread.start()

    pipeline_loop()
    server.wait_for_termination()

if __name__ == "__main__":
    logging.basicConfig()
    serve()
