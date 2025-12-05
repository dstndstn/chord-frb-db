This is a sketch/demo of using gRPC (google RPC) for communicating between the FRB Search
system and the FRB Sifter.

The assumption is that the FRB Search is running C++, and the FRB Sifter is running Python.

Unfortunately, it seems like the Ubuntu packages lag quite a bit behind the docs, at least the
example code on grpc.io ... so for Ubuntu 24.04 I had to install:

    wget https://launchpad.net/ubuntu/+archive/primary/+files/libabsl-dev_20240722.0-4ubuntu1_amd64.deb
    wget https://launchpad.net/ubuntu/+archive/primary/+files/libabsl20240722_20240722.0-4ubuntu1_amd64.deb
    wget https://launchpad.net/ubuntu/+archive/primary/+files/libgrpc++-dev_1.51.1-6build1_amd64.deb
    wget https://launchpad.net/ubuntu/+archive/primary/+files/libgrpc++1.51t64_1.51.1-6build1_amd64.deb
    wget https://launchpad.net/ubuntu/+archive/primary/+files/libgrpc-dev_1.51.1-6build1_amd64.deb
    wget https://launchpad.net/ubuntu/+archive/primary/+files/libgrpc29t64_1.51.1-6build1_amd64.deb
    wget https://launchpad.net/ubuntu/+archive/primary/+files/protobuf-compiler-grpc_1.51.1-6build1_amd64.deb
    wget https://launchpad.net/ubuntu/+archive/primary/+files/libre2-11_20250805-1build1_amd64.deb

and then `dpkg -i` install them.

The Makefile includes the "Hello world" demo, as well as an initial sketch of some FRB messages.

The FRB sifter demo is

python frb_sifter_server.py

and

./cpptest

There is also a python client test code:

python frb_sifter_test.py



