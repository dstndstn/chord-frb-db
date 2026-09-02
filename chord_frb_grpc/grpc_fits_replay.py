"""
CHIME FITS replay client — simulates N search nodes sending L1 events via gRPC.

Each node is assigned a disjoint subset of the 1024 CHIME beams and runs in its
own thread. Nodes send events file-by-file in sorted order; each unique timechunk
(by fpga count) within a file is sent as a single FrbEventsMessage.
Every node sends a message for every timechunk in every file, even if it has no
events for that timechunk, so the server can detect when all nodes have checked in.

Usage:
    python grpc_fits_replay.py \\
        --fits-dir ~/chord_sifter_testing/events \\
        --n-nodes 4 \\
        --server localhost:50051 \\
        [--n-files 10]
"""

import argparse
import os
import threading
import glob
import numpy as np
import fitsio

try:
    import grpc
    from chord_frb_grpc.frb_sifter_chime_pb2 import ConfigMessage, FrbEventsMessage, FrbEvent
    from chord_frb_grpc.frb_sifter_chime_pb2_grpc import FrbSifterChimeStub
except ImportError:
    raise ImportError(
        'chord_frb_grpc stubs not found. Generate them with:\n'
        '  cd chord_frb_grpc\n'
        '  python -m grpc_tools.protoc -I=. --python_out=. --pyi_out=. '
        '--grpc_python_out=. frb_sifter_chime.proto'
    )


def _build_beam_geometry():
    """Return (beam_to_dradec, beam_to_xygrid) dicts for all 1024 CHIME beams."""
    import cfbm
    from scipy import constants as phys_const

    all_beams = np.hstack([np.arange(256) + i * 1000 for i in range(4)])

    northmost_beam = 60.0
    delta_y_feed_m = 0.3048
    freq_ref = (phys_const.speed_of_light * 128
                / (np.sin(northmost_beam * np.pi / 180.0) * delta_y_feed_m * 256))
    Ny = 256
    reference_angles = np.rad2deg(
        np.arcsin(phys_const.speed_of_light * (np.arange(Ny) + 1 - Ny / 2.0)
                  / (freq_ref * Ny * delta_y_feed_m))
    )
    ew_spacing = [-0.4, 0, 0.4, 0.8]
    dra  = np.array(ew_spacing)[all_beams // 1000]
    ddec = reference_angles[all_beams % 1000]

    bm = cfbm.current_model_class()
    xg, yg = bm.get_cartesian_from_position(
        *bm.get_beam_positions(all_beams, freqs=bm.clamp_freq).squeeze().T
    )
    beam_to_dradec = {int(k): (float(v1), float(v2))
                      for k, v1, v2 in zip(all_beams, dra, ddec)}
    beam_to_xygrid = {int(k): (float(v1), float(v2))
                      for k, v1, v2 in zip(all_beams, xg, yg)}
    return beam_to_dradec, beam_to_xygrid


def _load_config_yaml():
    """Return a YAML string identifying this node's config for CheckConfiguration."""
    import yaml
    from pathlib import Path
    # Send the bonsai config filename as the config identifier.
    # The server validates all nodes agree on the same config string.
    bonsai_fn = 'bonsai_production_fixed_coarse_graining_hybrid_0.8_0.015.txt'
    config_dir = Path(__file__).parent.parent / 'chord_frb_sifter' / 'config'
    bonsai_path = config_dir / bonsai_fn
    with open(bonsai_path) as f:
        content = f.read()
    return yaml.dump({'bonsai_config': content})


def _row_to_proto_event(row, beam, beam_to_dradec, beam_to_xygrid, frame0_nano):
    dra, ddec = beam_to_dradec[beam]
    gx, gy    = beam_to_xygrid[beam]
    # timestamp_utc in FITS is empty (zero); compute from frame0_nano and fpga_timestamp
    timestamp_utc = int(frame0_nano/1000 + int(row['timestamp_fpga']) * 2.56)
    return FrbEvent(
        beam_id                = beam,
        fpga_timestamp         = int(row['timestamp_fpga']),
        dm                     = float(row['dm']),
        dm_error               = 0.0,
        snr                    = float(row['snr']),
        rfi_prob               = 0.0,
        timestamp_utc          = timestamp_utc,
        tree_index             = int(row['tree_index']),
        snr_scale              = float(row['snr_scale']),
        spectral_index         = int(row['spectral_index']),
        scattering_measure     = int(row['scattering_measure']),
        level1_nhits           = int(row['level1_nhits']),
        rfi_grade_level1       = int(row['rfi_grade_level1']),
        rfi_mask_fraction      = float(row['rfi_mask_fraction']),
        rfi_clip_fraction      = float(row['rfi_clip_fraction']),
        snr_vs_dm              = row['snr_vs_dm'].tolist(),
        snr_vs_tree_index      = row['snr_vs_tree_index'].tolist(),
        snr_vs_spectral_index  = row['snr_vs_spectral_index'].tolist(),
        beam_dra               = dra,
        beam_ddec              = ddec,
        beam_grid_x            = gx,
        beam_grid_y            = gy,
        is_incoherent          = False,
    )


def _node_thread(node_id, assigned_beams, fits_files, server_addr,
                 config_yaml, beam_to_dradec, beam_to_xygrid):
    assigned_set = set(int(b) for b in assigned_beams)
    channel = grpc.insecure_channel(server_addr)
    stub = FrbSifterChimeStub(channel)

    # Send config
    r = stub.CheckConfiguration(ConfigMessage(yaml=config_yaml))
    if not r.ok:
        print('Node %d: config rejected by server' % node_id)
        channel.close()
        return
    print('Node %d: config accepted' % node_id)

    for fn in fits_files:
        data = fitsio.read(fn)
        frame0_nano = int(data['frame0_nano'][0])

        # Collect all timechunks in this file before beam-filtering so every
        # node sends one message per timechunk regardless of whether it has events.
        all_timechunks = np.unique(data['fpga'])

        mask = np.isin(data['beam'], list(assigned_set))
        node_data = data[mask]

        for timechunk in all_timechunks:
            chunk_mask = node_data['fpga'] == timechunk
            chunk_data = node_data[chunk_mask]

            events = [
                _row_to_proto_event(chunk_data[i], int(chunk_data['beam'][i]),
                                    beam_to_dradec, beam_to_xygrid, frame0_nano)
                for i in range(len(chunk_data))
            ]

            msg = FrbEventsMessage(
                has_injections   = False,
                beam_set_id      = node_id,
                chunk_fpga_count = int(timechunk),
                frame0_nano      = frame0_nano,
                events           = events,
            )
            r = stub.FrbEvents(msg)
            if not r.ok:
                print('Node %d: FrbEvents rejected: %s' % (node_id, r.message))

    print('Node %d: finished all files' % node_id)
    channel.close()


def main():
    parser = argparse.ArgumentParser(description='CHIME FITS gRPC replay client')
    parser.add_argument('--fits-dir', required=True)
    parser.add_argument('--n-nodes', type=int, default=4)
    parser.add_argument('--server', default='localhost:50051')
    parser.add_argument('--n-files', type=int, default=None,
                        help='Limit number of FITS files (default: all)')
    parser.add_argument('--start-file', type=int, default=0,
                        help='Index of first file to replay (default: 0)')
    args = parser.parse_args()

    fits_files = sorted(glob.glob(os.path.join(args.fits_dir, '*.fits')))
    fits_files = fits_files[args.start_file:]
    if args.n_files:
        fits_files = fits_files[:args.n_files]
    if not fits_files:
        raise SystemExit('No FITS files found in %s' % args.fits_dir)
    print('Replaying %d FITS file(s) as %d node(s)' % (len(fits_files), args.n_nodes))

    from chord_frb_sifter.chime_test_pipeline import setup
    setup()

    print('Building beam geometry...')
    beam_to_dradec, beam_to_xygrid = _build_beam_geometry()

    config_yaml = _load_config_yaml()

    all_beams = np.hstack([np.arange(256) + i * 1000 for i in range(4)])
    node_beams = np.array_split(all_beams, args.n_nodes)

    threads = []
    for node_id, assigned_beams in enumerate(node_beams):
        t = threading.Thread(
            target=_node_thread,
            args=(node_id, assigned_beams, fits_files, args.server,
                  config_yaml, beam_to_dradec, beam_to_xygrid),
            daemon=True,
        )
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print('All nodes finished.')


if __name__ == '__main__':
    main()
