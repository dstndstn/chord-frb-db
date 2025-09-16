

# pip install grpcio
# pip install grpcio-tools

all: 
.PHONY: all

HELLO := helloworld_pb2.py helloworld_pb2.pyi helloworld_pb2_grpc.py
all: $(HELLO)

#world_pb2.py helloworld_pb2.pyi helloworld_grpc.py: helloworld.proto

#$(HELLO): helloworld.proto
#	python -m grpc_tools.protoc -I=. --python_out=. --pyi_out=. --grpc_python_out=. helloworld.proto

%_pb2.py %_pb2.pyi %_pb2_grpc.py: %.proto
	python -m grpc_tools.protoc -I=. --python_out=. --pyi_out=. --grpc_python_out=. $<

clean:
	rm $(HELLO)
.PHONE: clean
