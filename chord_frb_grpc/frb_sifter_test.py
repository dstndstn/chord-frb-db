import yaml
from chord_frb_grpc.frb_sifter_server import FrbSifter, serve

import grpc
from chord_frb_grpc.frb_sifter_pb2 import ConfigMessage, FrbEventsMessage, FrbEvent
from chord_frb_grpc.frb_sifter_pb2_grpc import FrbSifterStub

if __name__ == '__main__':
    import logging
    logging.basicConfig()
    port = 50051
    sifter = FrbSifter()
    server = serve(sifter, port=port)

    sifter_addr = 'localhost:' + str(port)

    yaml_config = {'config_item': 42, 'other_thing': 900.}

    yaml_config_str = yaml.dump(yaml_config)
    
    # FRB Search node 1
    ch1 = grpc.insecure_channel(sifter_addr)
    stub1 = FrbSifterStub(ch1)
    msg = ConfigMessage(yaml=yaml_config_str);
    r1 = stub1.CheckConfiguration(msg)
    print('Got config check result:', r1)

    # FRB Search node 2
    ch2 = grpc.insecure_channel(sifter_addr)
    stub2 = FrbSifterStub(ch2)
    msg = ConfigMessage(yaml=yaml_config_str);
    r2 = stub2.CheckConfiguration(msg)
    print('Got config check result:', r2)

    
    server.wait_for_termination()

