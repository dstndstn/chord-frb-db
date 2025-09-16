

# pip install grpcio
# pip install grpcio-tools

all: 
.PHONY: all

HELLO := helloworld_pb2.py helloworld_pb2.pyi helloworld_pb2_grpc.py
all: $(HELLO)

SIFTER := frb_sifter_pb2.py frb_sifter_pb2.pyi frb_sifter_pb2_grpc.py
all: $(SIFTER)

%_pb2.py %_pb2.pyi %_pb2_grpc.py: %.proto
	python -m grpc_tools.protoc -I=. --python_out=. --pyi_out=. --grpc_python_out=. $<

clean:
	rm $(HELLO)
.PHONE: clean
