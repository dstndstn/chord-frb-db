import yaml
from chord_frb_grpc.frb_sifter_server import FrbSifter, serve

import grpc
from chord_frb_grpc.frb_sifter_pb2 import ConfigMessage, FrbEventsMessage, FrbEvent
from chord_frb_grpc.frb_sifter_pb2_grpc import FrbSifterStub

if __name__ == '__main__':
    import logging
    logging.basicConfig()
    port = 50051
    injections = False

    fpga_counts_per_sec = 390625
    
    sifter = FrbSifter(injections)
    server = serve(sifter, port=port)

    sifter_addr = 'localhost:' + str(port)

    yaml_config = {'config_item': 42, 'other_thing': 900.}

    yaml_config_str = yaml.dump(yaml_config)
    
    # FRB Search node 1
    ch1 = grpc.insecure_channel(sifter_addr)
    stub1 = FrbSifterStub(ch1)
    msg = ConfigMessage(yaml=yaml_config_str)
    r1 = stub1.CheckConfiguration(msg)
    print('Got config check result:', r1.ok)
    assert(r1.ok)

    # FRB Search node 2
    ch2 = grpc.insecure_channel(sifter_addr)
    stub2 = FrbSifterStub(ch2)
    msg = ConfigMessage(yaml=yaml_config_str)
    r2 = stub2.CheckConfiguration(msg)
    print('Got config check result:', r2.ok)
    assert(r2.ok)

    yaml_config.update({'another_thing':17})
    yaml_2 = yaml.dump(yaml_config)

    # FRB Search node 3
    ch3 = grpc.insecure_channel(sifter_addr)
    stub3 = FrbSifterStub(ch3)
    msg = ConfigMessage(yaml=yaml_2)
    r3 = stub3.CheckConfiguration(msg)
    print('Got config check result:', r3.ok)
    assert(not(r3.ok))

    # FRB events
    events = []
    chunk_fpga = fpga_counts_per_sec * 10
    msg = FrbEventsMessage(has_injections=not(injections),
                           beam_set_id = 1,
                           chunk_fpga_count = chunk_fpga,
                           events = [])
    r1 = stub1.FrbEvents(msg)
    print('Got FRB events reply:', r1.ok, r1.message)
    assert(not(r1.ok))

    events = []
    chunk_fpga = fpga_counts_per_sec * 10
    for b in range(10):
        events.append(FrbEvent(beam_id=b,
                               fpga_timestamp = chunk_fpga, # + ...
                               dm = 100.,
                               dm_error = 1.0,
                               snr = 8.,
                               rfi_prob = 0.1))

    msg = FrbEventsMessage(has_injections=injections,
                           beam_set_id = 1,
                           chunk_fpga_count = chunk_fpga,
                           events = events)
    r1 = stub1.FrbEvents(msg)
    print('Got FRB events reply:', r1)

    ch1.close()
    ch2.close()
    ch3.close()

    grace = 1.
    server.stop(grace)
    server.wait_for_termination()

