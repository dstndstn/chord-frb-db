

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

CPPTEST := cpptest
all: $(CPPTEST)

CPPFLAGS += `pkg-config --cflags protobuf grpc absl_flags absl_flags_parse`
CXXFLAGS += -std=c++17

HOST_SYSTEM = $(shell uname | cut -f 1 -d_)
SYSTEM ?= $(HOST_SYSTEM)

#LDFLAGS += -L/usr/local/lib `pkg-config --libs --static protobuf grpc++ absl_flags absl_flags_parse absl_log_initialize $(PROTOBUF_ABSL_DEPS)`\

ifeq ($(SYSTEM),Darwin)
LDFLAGS += `pkg-config --libs --static protobuf grpc++ absl_flags absl_flags_parse absl_log_initialize $(PROTOBUF_ABSL_DEPS)`\
           $(PROTOBUF_UTF8_RANGE_LINK_LIBS) \
           -pthread\
           -lgrpc++_reflection\
           -ldl
else
LDFLAGS += -L/usr/local/lib `pkg-config --libs --static protobuf grpc++ absl_flags absl_flags_parse absl_log_initialize $(PROTOBUF_ABSL_DEPS)`\
           $(PROTOBUF_UTF8_RANGE_LINK_LIBS) \
           -pthread\
           -Wl,--no-as-needed -lgrpc++_reflection -Wl,--as-needed\
           -ldl
endif

cpptest: cpptest.o frb_sifter.pb.o frb_sifter.grpc.pb.o
	$(CXX) $^ $(LDFLAGS) -o $@

PROTOC = protoc
GRPC_CPP_PLUGIN = grpc_cpp_plugin
GRPC_CPP_PLUGIN_PATH ?= $(shell which $(GRPC_CPP_PLUGIN))

.PRECIOUS: %.grpc.pb.cc
%.grpc.pb.cc: %.proto
	$(PROTOC) --grpc_out=. --plugin=protoc-gen-grpc=$(GRPC_CPP_PLUGIN_PATH) $<

.PRECIOUS: %.pb.cc
%.pb.cc: %.proto
	$(PROTOC) --cpp_out=. $<

clean:
	rm $(HELLO)
.PHONE: clean
