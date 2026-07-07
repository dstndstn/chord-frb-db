This is a sketch/demo of using gRPC (google RPC) for communicating between the FRB Search
system and the FRB Sifter.

The assumption is that the FRB Search is running C++, and the FRB Sifter is running Python.

.proto file format:
https://protobuf.dev/programming-guides/proto3/

Overview:
https://protobuf.dev/overview/

Unfortunately, it seems like the Ubuntu packages lag quite a bit behind the docs, at least the
example code on grpc.io ... so for Ubuntu 24.04 I had to install:

    # Some package versions in Ubuntu are okay:
    apt install libprotobuf32t64 libc-ares-dev libre2-dev libprotoc32t64 protobuf-compiler libre2-10 libprotobuf-dev

    # but need newer:
    wget https://launchpad.net/ubuntu/+archive/primary/+files/libabsl-dev_20240722.0-4ubuntu1_amd64.deb
    wget https://launchpad.net/ubuntu/+archive/primary/+files/libabsl20240722_20240722.0-4ubuntu1_amd64.deb
    wget https://launchpad.net/ubuntu/+archive/primary/+files/libgrpc++-dev_1.51.1-6build1_amd64.deb
    wget https://launchpad.net/ubuntu/+archive/primary/+files/libgrpc++1.51t64_1.51.1-6build1_amd64.deb
    wget https://launchpad.net/ubuntu/+archive/primary/+files/libgrpc-dev_1.51.1-6build1_amd64.deb
    wget https://launchpad.net/ubuntu/+archive/primary/+files/libgrpc29t64_1.51.1-6build1_amd64.deb
    wget https://launchpad.net/ubuntu/+archive/primary/+files/protobuf-compiler-grpc_1.51.1-6build1_amd64.deb
    wget https://launchpad.net/ubuntu/+archive/primary/+files/libre2-11_20250805-1build1_amd64.deb

and then `dpkg -i` install them:

    sudo dpkg -i *.deb

And then,

    pip install grpcio-tools --break-system-packages

The Makefile includes the "Hello world" demo, as well as an initial sketch of some FRB messages.

The FRB sifter demo is

python frb_sifter_server.py

and

./cpptest

There is also a python client test code:

python frb_sifter_test.py



