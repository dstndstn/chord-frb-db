# Copyright 2015 gRPC authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
"""The Python implementation of the GRPC helloworld.Greeter client."""
# from grpc:examples/python/helloworld/greeter_client.py

import logging

import grpc
import helloworld_pb2
import helloworld_pb2_grpc

def run():
    print("Will try to greet world ...")
    with grpc.insecure_channel("localhost:50051") as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)
        for i in range(100):
            response = stub.SayHello(helloworld_pb2.HelloRequest(name="you%i" % i))
            print("Greeter client received: " + response.message)

def run_async():
    print('Sending messages (async)...')
    with grpc.insecure_channel("localhost:50051") as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)
        futures = []
        for i in range(100):
            response = stub.SayHello.future(helloworld_pb2.HelloRequest(name="msg%i" % i))
            futures.append(response)
        print('Waiting for async replies...')
        for f in futures:
            print('Reply:', f.result().message)

if __name__ == "__main__":
    logging.basicConfig()
    #run()
    run_async()
