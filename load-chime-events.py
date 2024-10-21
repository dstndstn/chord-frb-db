import sys
#from tqdm import tqdm

import os
from os import path

from frb_L2_L3 import config_dir
import time

from copy import deepcopy

# L4 actors
#from l4_pipeline.interfaces.L3_headers.register_event import RegisterEvent
# from l4_pipeline.interfaces.L3_headers.write_header import WriteHeader
# from l4_pipeline.interfaces.L3_headers.send_to_frb_master import SendToFRBMaster
# from l4_pipeline.interfaces.L3_headers.action_throttler import ActionThrottler
# from l4_pipeline.interfaces.multiwavelength_maps.map_maker import MapMaker
# from l4_pipeline.interfaces.vo_event_sender.vo_event_sender import VOEventSender
# from l4_pipeline.interfaces.L1_intensity.intensity_callback_initiator import IntensityCallbackInitiator
# from l4_pipeline.interfaces.L1_intensity.cascade_maker import CascadeMaker
# from l4_pipeline.interfaces.L0_baseband.alert_outriggers import AlertOutriggers
# from l4_pipeline.interfaces.L0_baseband.baseband_callback_initiator import BasebandCallbackInitiator
# from l4_pipeline.interfaces.L0_baseband.baseband_analysis import BasebandAnalysis
# from l4_pipeline.interfaces.L0_baseband.pathfinder_callback_initiator import PathfinderCallbackInitiator
from frb_common.events.l1_event.dtypes import L1_EVENT_DTYPE

import fitsio
import numpy as np
import pickle
from collections import Counter

def read_fits_events(fn):
    from frb_common.events import L1Event
    events = fitsio.read(fn)
    print('events:', len(events), events.dtype)

    #dtype = L1_EVENT_DTYPE + [('pipeline_id', np.int64)]
    #newevents = np.zeros(len(events), dtype)

    newevents = np.zeros(len(events), L1_EVENT_DTYPE)
    for k in events.dtype.names:
        if k in ['frame0_nano', 'beam', 'fpga']:
            continue
        newevents[k] = events[k]
    beams = events['beam']
    fpgas = events['fpga']
    frame0nano = events['frame0_nano']
    # compute timestamp_fpga to timestamp_utc (in micro-seconds)
    # ASSUME 2.56 microseconds per FPGA sample
    newevents['timestamp_utc'] = frame0nano/1000. + events['timestamp_fpga'] * 2.56

    events = newevents
    events = L1Event(events)
    events = events.demote()
    print('Final event type:', events.dtype)
    print('Event timestamp_utc:', events['timestamp_utc'])
    return fpgas,beams,events

def get_db_engine():
    from sqlalchemy import create_engine
    from chord_frb_db.models import Base
    db_url = os.environ.get('CHORD_FRB_DB_URL', 'sqlite+pysqlite:///db.sqlite3')
    print('Using database URL:', db_url)
    engine = create_engine(db_url, echo=True)
    if 'sqlite' in db_url:
        # Make sure database tables exist
        Base.metadata.create_all(engine)
    return engine

def mainB():
    '''
    export PYTHONPATH=${PYTHONPATH}:../frb_common/:../L4_pipeline/:../L4_databases/
    '''

    # L4 pipeline
    # import l4_pipeline.interfaces.config as cfg
    # config_dir = os.path.dirname(os.path.realpath(cfg.__file__))
    # print('Config_dir', config_dir)
    # config_path = os.path.join(config_dir, "precommissioning_on_site.yaml")
    # pipeline.load_configuration(config_path)
    # l4_pipeline = []
    # for name,clz in [('RegisterEvent', RegisterEvent),
    #                  ]:
    from frb_common import pipeline_tools

    from sqlalchemy.orm import Session
    from chord_frb_db.models import Base

    engine = get_db_engine()
    setup()

    from frb_L2_L3.actors.beam_buffer import BeamBuffer
    from frb_L2_L3.actors.beam_grouper import BeamGrouper
    from frb_L2_L3.actors.event_maker import EventMaker
    from frb_L2_L3.actors.rfi_sifter import RFISifter
    from frb_L2_L3.actors.localizer import Localizer
    from frb_L2_L3.actors.known_source_sifter import KnownSourceSifter
    from frb_L2_L3.actors.dm_checker import DMChecker
    from frb_L2_L3.actors.flux_estimator import FluxEstimator
    from frb_L2_L3.actors.action_picker import ActionPicker
    #from frb_L2_L3.actors.slowpoke_catcher import SlowpokeCatcher
    #from frb_L2_L3.actors.injection_snatcher import InjectionSnatcher
    #from frb_L2_L3.actors.exit_handler import ExitHandler
    
    pipeline = []
    for name,clz in [('BeamBuffer', BeamBuffer),
                     ('BeamGrouper', BeamGrouper),
                     ('EventMaker', EventMaker),
                     ('RFISifter', RFISifter),
                     ('Localizer', Localizer),
                     ('KnownSourceSifter', KnownSourceSifter),
                     ('DMChecker', DMChecker),
                     ('FluxEstimator', FluxEstimator),
                     ('ActionPicker', ActionPicker),
        #('InjectionSnatcher', InjectionSnatcher),
        #('SlowpokeCatcher', SlowpokeCatcher),
        #('ExitHandler', ExitHandler),
                     ]:
        conf = pipeline_tools.get_worker_configuration(name)
        #print('conf:', conf)
        conf.pop('io')
        conf.pop('log')
        picl = conf.pop('use_pickle')
        conf.pop('timeout')
        conf.pop('periodic_update')
        p = clz(**conf)
        picl = False
        unpickle_output = (name == 'BeamGrouper')
        pipeline.append((p,picl,unpickle_output))

    all_payloads = []

    for file_num in range(3):
        fn = 'events/events-%03i.fits' % file_num
        fpgas,beams,events = read_fits_events(fn)
        #fpga_start = int(events.timestamp_fpga.min())

        # FIXME -- could assume events files are sorted by FPGA and time....
        u_fpgas = np.unique(fpgas)
        for fpga in u_fpgas:
            I = np.flatnonzero(fpgas == fpga)
            e = events[I]
            b = beams[I]
            ubeams = np.unique(b)
            print(len(I), 'events for FPGA', fpga, 'in', len(ubeams), 'beams')
            for beam in ubeams:
                # Events for this FPGA and beam number
                J = np.flatnonzero(b == beam)
                beam_events = e[J]
                events_string = b''.join([e.tobytes() for e in beam_events])
                event_data = [str(beam).encode(), str(fpga).encode(), events_string]
                outputs = process_events(pipeline, event_data)
                print('Outputs:', outputs)
                if len(outputs):

                    # transaction block
                    #with engine.begin() as conn:
                    #    send_to_db(conn, outputs)
                    #    # automatic commit on exit
                    with Session(engine) as session:
                        payloads = send_to_db(session, outputs)

                    all_payloads.extend(payloads)

    f = open('payloads.pickle', 'wb')
    pickle.dump(all_payloads, f)
    f.close()
    
                    
def send_to_db(session, outputs):
    # outputs are like [[<frb_common.events.l2_event.l2_event.L2Event object at 0x123fc4190>],

    from chord_frb_db.models import EventBeam, Event

    # Not setting in DB:
    #

    # Not using from pipeline:
    # timestamp_utc (it's wrong?)
    # snr_scale (what is it)
    # spectral_index
    # scattering_measure
    # level1_nhits
    # snr_vs_dm
    # snr_vs_tree_index
    # snr_vs_spectral_index
    # is_incoherent
    # snr_vs_dm_x
    # snr_vs_tree_index_x
    # snr_vs_spectral_index_x
    l1_name_map = {
        'beam_no': 'beam',
        'snr': True,
        'timestamp_fpga': True,
        'timestamp_utc': True,
        'time_error': True,
        'tree_index': True,
        'rfi_grade_level1': 'rfi_grade',
        'rfi_mask_fraction': True,
        'rfi_clip_fraction': True,
        'dm': True,
        'dm_error': True,
        'pos_ra_deg': 'ra',
        'pos_ra_error_deg': 'ra_error',
        'pos_dec_deg': 'dec',
        'pos_dec_error_deg': 'dec_error',
    }

    # Not setting:
    # is_known
    # is_frb
    # best_beam
    # best_snr
    # pos_error_theta_deg_68 --> assert == 0?
    # known_source_name
    # known_source_rating -1
    # known_source_metrics {}
    # beam_sensitivity{,_min_95,_max_95}
    # spectral_index_error
    # flux_mjy_{min,max}
    # rfi_grade_level2
    # beam_activity
    # unknown_event_type
    # coh_dm_activity
    # avg_l1_grade

    # Ignoring L2 event fields:
    # scattering
    # fluence

    l2_name_map = {
        'timestamp_utc': 'timestamp',
        'combined_snr': 'total_snr',
        'dm': True,
        'dm_error': True,
        'pos_ra_deg': 'ra',
        'pos_error_semimajor_deg_68': 'ra_error',
        'pos_dec_deg': 'dec',
        'pos_error_semiminor_deg_68': 'dec_error',
        'dm_gal_ne_2001_max': 'dm_ne2001',
        'dm_gal_ymw_2016_max': 'dm_ymw2016',
        'spectral_index': True,
        'pulse_width_ms': 'pulse_width',
        'rfi_grade_level2': 'rfi_grade',
        'beam_activity': True,
    }
    #'flux_mjy': 'flux',

    payloads = []

    for olist in outputs:
        out_payloads = []
        payloads.append(out_payloads)
        for event in olist:

            l2_db_args = { 'is_rfi': False,
                           'is_known_pulsar': False,
                           'is_new_burst': False,
                           'is_frb': False,
                           'is_repeating_frb': False,
                           'scattering': 0.,
                           'fluence': 0.,
                           }
            #l1_event_ids = []
            l1_objs = []

            payload = event.database_payload()
            out_payloads.append(payload.copy())

            print('DB payload:')
            for k,v in payload.items():
                # skip...
                if k in ['dead_beam_nos']:
                    continue
                if k == 'l1_events':
                    print(' ', k, ':', len(v))
                    for l1 in v:

                        l1_db_args = {}

                        print('  L1 Event:')
                        for l1k,l1v in l1.items():
                            print('    ', l1k, l1v)

                            if l1k == 'timestamp_utc':
                                l1v = l1v.timestamp()

                            k2 = l1_name_map.get(l1k, None)
                            if k2 is not None:
                                # same key name
                                if k2 is True:
                                    k2 = l1k
                                l1_db_args[k2] = l1v

                        #for k,v in l1_db_args.items():
                        #    print('  L1:', k, '=', type(v), v)
                        l1_db_obj = EventBeam(**l1_db_args)
                        print('Created L1 db object:', l1_db_obj)
                        session.add(l1_db_obj)
                        session.flush()
                        print('L1 db id:', l1_db_obj.id)
                        assert(l1_db_obj.id is not None)
                        #l1_event_ids.append(l1_db_obj.id)
                        l1_objs.append(l1_db_obj)
                        #session.commit()
                    continue
                if isinstance(v, (np.float32, np.float64)):
                    v = float(v)
                print(' ', k, v)

                if k == 'timestamp_utc':
                    v = v.timestamp()
                k2 = l2_name_map.get(k, None)
                if k2 is not None:
                    # same key name
                    if k2 is True:
                        k2 = k
                    l2_db_args[k2] = v
                if k == 'known_source_name':
                    print('Known source!')
                if k == 'event_category':
                    if v == 3:
                        l2_db_args['is_rfi'] = True
                if k == 'flux_mjy':
                    # milli -> Jansky
                    l2_db_args['flux'] = 0.001 * v

            #l2_db_args['nbeams'] = len(l1_event_ids)
            l2_db_args['nbeams'] = len(l1_objs)

            for k,v in l2_db_args.items():
                print(' L2:', k, '=', type(v), v)

            l2_db_obj = Event(**l2_db_args)
            print('Created L2 db object:', l2_db_obj)
            session.add(l2_db_obj)
            #print('L1 event ids:', l1_event_ids)
            print('L2 beams:', l2_db_obj.beams)
            #for b in l1_event_ids:
            #    l2_db_obj.beams.append(b)
            for e in l1_objs:
                l2_db_obj.beams.append(e)
            session.flush()
            print('L2 db id:', l2_db_obj.event_id)
            print('L2 beam ids:', l2_db_obj.beams)
            print('L1 events:', l1_objs)
            print('  L1 back-pointers:', [e.event_id for e in l1_objs])
            session.commit()

        print('Output payloads:', len(out_payloads))
    print('Payloads:', len(payloads))

    return payloads
            
''' L1 events:
     l1_timestamp 0.0
     pipeline_timestamp 679750.600012863
     pipeline_id 5
     beam_no 8
     timestamp_utc 1970-01-01 00:00:00
     timestamp_fpga 390856485888
     tree_index 0
     snr 10.849896430969238
     snr_scale 0.0
     dm 19.81433868408203
     spectral_index 0
     scattering_measure 0
     level1_nhits 0
     rfi_grade_level1 0
     rfi_mask_fraction 0.0
     rfi_clip_fraction 0.0
     snr_vs_dm [7.296021461486816, 6.753296375274658, 6.06824254989624, 5.921223163604736, 6.197881698608398, 7.471080780029297, 6.574099540710449, 8.159812927246094, 10.849896430969238, 7.941225051879883, 5.595312118530273, 7.371004104614258, 5.885530948638916, 6.015096187591553, 6.846845626831055, 5.988121032714844, 6.786647796630859]
     snr_vs_tree_index [10.849896430969238, 10.266348838806152, 0.0, 0.0, 0.0]
     snr_vs_spectral_index [10.849896430969238, 8.581052780151367]
     time_error 0.00786431971937418
     dm_error 0.40437427163124084
     pos_ra_deg 341.4575500488281
     pos_dec_deg -4.146359920501709
     pos_ra_error_deg 0.4806761145591736
     pos_dec_error_deg 0.8136351704597473
     is_incoherent False
     snr_vs_dm_x [16.579343795776367, 16.983718872070312, 17.388093948364258, 17.79246711730957, 18.196842193603516, 18.601215362548828, 19.005590438842773, 19.409963607788086, 19.81433868408203, 20.218713760375977, 20.62308692932129, 21.027462005615234, 21.431835174560547, 21.836210250854492, 22.240583419799805, 22.64495849609375, 23.049333572387695]
     snr_vs_tree_index_x [0.0, 0.0, 0.0, 0.0, 0.0]
     snr_vs_spectral_index_x [-3.0, 3.0]
     
'''
            
'''
L3 event:
list of L1 events

  timestamp_utc 1970-01-01 00:00:00+00:00
  combined_snr 13.975885
  beam_sensitivity 0.1264353532689731
  beam_sensitivity_min_95 0.0055235227409198935
  beam_sensitivity_max_95 0.12735711126662194
  flux_mjy 6635.414853517661
  flux_mjy_min_95 6543.348675854158
  flux_mjy_max_95 152902.43137003513
  pulse_width_ms 0.49151998246088624
  dm 19.814339
  dm_error 0.40437427
  spectral_index 0.0
  spectral_index_error 4.0
  rfi_grade_level2 10.0
  rfi_grade_metrics_level2 {}
  pos_ra_deg 341.4635913471214
  pos_dec_deg -2.231904521712195
  pos_error_semimajor_deg_68 0.4052587554112179
  pos_error_semimajor_deg_95 0.7943071606059872
  pos_error_semiminor_deg_68 0.2358026254396334
  pos_error_semiminor_deg_95 0.46217314586168146
  pos_error_theta_deg_68 0.0
  pos_error_theta_deg_95 0.0
  known_source_name
  known_source_rating -1
  known_source_metrics {}
  dm_gal_ne_2001_max 34.9819916452506
  dm_gal_ymw_2016_max 25.60786075834742
  beam_activity 16
  unknown_event_type 0
  event_category 1
  version XXX
  actions {'GET_INTENSITY': {'REQUEST': False}, 'GET_BASEBAND': {'REQUEST': False}, 'ALERT_PULSAR': {'REQUEST': False}, 'ALERT_COMMUNITY': {'REQUEST': False}, 'SEND_HEADER': {'REQUEST': True}}
  event_status {'BeamGrouper': 0, 'RFISifter': 0, 'Localizer': 0, 'KnownSourceSifter': 0, 'DMChecker': 0, 'FluxEstimator': 0, 'ActionPicker': 0}
  pipeline_mode {'BeamGrouper': -1, 'RFISifter': 2, 'Localizer': 2, 'KnownSourceSifter': 2, 'DMChecker': 2, 'FluxEstimator': 2, 'ActionPicker': 2}
  is_test False
  futures {'coh_dm_activity': 276, 'dm_activity_lookback': [0, 0, 0, 0, 0, 0, 0, 0, 0, 276], 'beam_activity_lookback': [0, 0, 0, 0, 0, 0, 0, 0, 0, 16], 'incoh_dm_activity': 0, 'dm_std': 41.658413, 'avg_l1_grade': 0.020357803824799507, 'trash_at_exit': False}
  event_processing_start_time 1724963214.8027909
'''
'''
  L1 Event:
     l1_timestamp 0.0
     pipeline_timestamp 327984.978451527
     pipeline_id 1093
     beam_no 11
     timestamp_utc 1970-01-01 00:00:00
     timestamp_fpga 390856731648
     tree_index 0
     snr 13.975885391235352
     snr_scale 0.0
     dm 19.81433868408203
     spectral_index 0
     scattering_measure 0
     level1_nhits 0
     rfi_grade_level1 0
     rfi_mask_fraction 0.0
     rfi_clip_fraction 0.0
     snr_vs_dm [12.128884315490723, 9.697505950927734, 7.5382080078125, 9.464571952819824, 8.81373119354248, 8.495182037353516, 8.880011558532715, 9.691327095031738, 13.975885391235352, 11.18685531616211, 8.045234680175781, 8.006065368652344, 7.89288330078125, 7.369781017303467, 9.25119686126709, 9.955826759338379, 8.459622383117676]
     snr_vs_tree_index [13.975885391235352, 12.649748802185059, 7.9205121994018555, 0.0, 0.0]
     snr_vs_spectral_index [13.975885391235352, 11.834529876708984]
     time_error 0.00786431971937418
     dm_error 0.40437427163124084
     pos_ra_deg 341.4533996582031
     pos_dec_deg -2.228651762008667
     pos_ra_error_deg 0.4806761145591736
     pos_dec_error_deg 0.7724871039390564
     is_incoherent False
     snr_vs_dm_x [16.579343795776367, 16.983718872070312, 17.388093948364258, 17.79246711730957, 18.196842193603516, 18.601215362548828, 19.005590438842773, 19.409963607788086, 19.81433868408203, 20.218713760375977, 20.62308692932129, 21.027462005615234, 21.431835174560547, 21.836210250854492, 22.240583419799805, 22.64495849609375, 23.049333572387695]
     snr_vs_tree_index_x [0.0, 0.0, 0.0, 0.0, 0.0]
     snr_vs_spectral_index_x [-3.0, 3.0]
'''



            
def process_events(pipeline, e):
    # e: event tuple
    input_events = [e]
    output_events = []
    for actor,picl,unpicl_out in pipeline:
        print('Running pipeline stage', actor.process_name)
        output_events = []
        for in_item in input_events:
            #print('Input to', actor.process_name, ':', in_item)
            if picl:
                in_item = [pickle.loads(x, encoding="latin1") for x in in_item]
            if len(in_item) == 1:
                in_item = in_item[0]

            in_item = deepcopy(in_item)
            #print('in_item deepcopy:', in_item)
            items = actor.perform_action(in_item)
            #print('Produced output:', items)
            if items is None:
                continue

            tnow = time.monotonic()
            for item in items:

                try:
                    #print('l1_events dtype:', item.l1_events.dtype)
                    #print('l1 timestamps:', item.l1_events['pipeline_timestamp'])

                    #t = item.l1_events['pipeline_timestamp']
                    t = item.l1_events['l1_timestamp']
                    pid = item.l1_events['pipeline_id']
                    for i in range(len(pid)):
                        print('Stage %s: Elapsed Time for %i: %.3f sec' % (actor.process_name, pid[i], tnow - t[i]))

                except:
                    pass

                if item is None:
                    continue

                if not isinstance(item, (list, tuple)):
                    item = [item]
                #print('Output from', actor.process_name, ':', item)
                if picl:
                    item = [pickle.dumps(x, protocol=2) for x in item]
                if unpicl_out:
                    item = [pickle.loads(x, encoding="latin1") for x in item]

                output_events.append(item)
        if len(output_events) == 0:
            break
        input_events = output_events

    # end of pipeline
    outputs = []
    for out_list in output_events:
        outx = []
        for out in out_list:
            try:
                out = pickle.loads(out, encoding="latin1")
            except:
                pass
            # try:
            #     out = out.database_payload()
            # except:
            #     pass
            outx.append(out)
        outputs.append(outx)
    return outputs
    
def setup():
    from frb_common import pipeline_tools as pipeline
    # all pipeline behaviour is encoded in config file
    config_path = path.join(config_dir, "drao_epsilon_pipeline_local.yaml")
    pipeline.load_configuration(config_path)
    setup_L1_event()
    
def setup_L1_event():
    from frb_common import pipeline_tools as pipeline
    from frb_common.events import L1Event
    bonsai_config = pipeline.config["generics"]["bonsai_config"]
    L1Event.use_bonsai_config(bonsai_config)

def mainA():
    from frb_L2_L3.utils import L1Simulator
    from frb_L2_L3 import sample_events_dir
    events = np.load(path.join(sample_events_dir, "stress_sample.npy"))
    print('Loaded events:', events)
    print('Number of events:', len(events))
    events = events[:4000]
    print('Number of events:', len(events))

    setup()

    # upgrade events...
    print('Saved event dtype', events.dtype)
    newevents = np.zeros(len(events), L1_EVENT_DTYPE)
    for k in events.dtype.names:
        newevents[k] = events[k]
    events = newevents
    print('Saved event dtype 2', events.dtype)
    events = L1Event(events)
    events = events.demote()

    pl = []
    for name,clz in [('BeamBuffer', BeamBuffer),
                     ('BeamGrouper', BeamGrouper),
                     ('EventMaker', EventMaker),
                     ('RFISifter', RFISifter),
                     ('Localizer', Localizer),
                     ('KnownSourceSifter', KnownSourceSifter),
                     ('DMChecker', DMChecker),
                     ('FluxEstimator', FluxEstimator),
                     ('ActionPicker', ActionPicker),
                     ('InjectionSnatcher', InjectionSnatcher),
                     ('SlowpokeCatcher', SlowpokeCatcher),
                     ('ExitHandler', ExitHandler),
                     ]:
        conf = pipeline.get_worker_configuration(name)
        print('conf:', conf)
        conf.pop('io')
        conf.pop('log')
        picl = conf.pop('use_pickle')
        conf.pop('timeout')
        conf.pop('periodic_update')
        p = clz(**conf)

        picl = False
        unpickle_output = (name == 'BeamGrouper')

        pl.append((p,picl,unpickle_output))

    tchunk = 8.0
    speedup = 80.
    tsleep = tchunk / speedup

    t_keys = events.timestamp_utc.astype(int) // int(1e6 * tchunk)
    b_keys = events.beam_no
    lookup = {}
    # for tk, bk, v in zip(t_keys, b_keys, [e.tostring() for e in events]):
    #     lookup.setdefault(tk, {})
    #     lookup[tk][bk] = lookup[tk].get(bk, b"") + v
    for tk, bk, v in zip(t_keys, b_keys, events):
        lookup.setdefault(tk, {})
        lookup[tk].setdefault(bk, [])
        lookup[tk][bk].append(v)
    fpga_start = int(events.timestamp_fpga.min())

    it0 = min(lookup.keys())

    beam_ids = 1000 * (np.arange(1024) // 256) + np.arange(1024) % 256

    sleep_deficit = 0.

    total_treal = 0.
    total_tspent = 0.

    pipeline_output = []
    
    #for it in tqdm(sorted(lookup.keys())):
    for it in sorted(lookup.keys()):
        t0 = time.time()

        fpga_stamp = fpga_start + int(it - it0) * int(tchunk / 2.56e-6)
        time_set = lookup.get(it, {})

        #for e in events:
        #e = e.tostring()
        #print('Event (stringified):', e)
        print('Running event', it)

        for beam in beam_ids:

            tnow = time.monotonic()
            events = time_set.get(beam, [])
            for e in events:
                e['l1_timestamp'] = tnow
            events_string = b"".join([e.tostring() for e in events])

            e = [str(beam).encode(), str(fpga_stamp).encode(), events_string]
            #print('Running event key', it, 'beam', beam)

            outputs = process_events(pl, e)
            pipeline_output.extend(outputs)
        # end of beams
                
        dt = time.time() - t0

        total_tspent += dt
        total_treal += tchunk
        print('Running on average at %.1f x speed' % (total_treal / total_tspent))
        
        print('Ran this event at %.1f x speed' % (tchunk / dt))
        print('Sleeping', tsleep-dt, '; sleep deficit', sleep_deficit)
        sleep = tsleep - dt
        if sleep > 0 and sleep_deficit > 0:
            # We ran faster than expected; pay back "sleep deficit" if we have any.
            payback = min(sleep, sleep_deficit)
            sleep -= payback
            sleep_deficit -= payback
        if sleep < 0:
            sleep_deficit += -sleep
        else:
            time.sleep(sleep)

    open('simple-output.picl', 'wb').write(pickle.dumps(pipeline_output))
                
if __name__ == '__main__':
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from chord_frb_db.models import Base, EventBeam, Event
    from sqlalchemy import delete

    engine = get_db_engine()

    #mainA()

    # Drop all existing data!!!

    print('Dropping existing event data...')
    with Session(engine) as session:
        st = delete(EventBeam)
        session.execute(st)
        st = delete(Event)
        session.execute(st)
        session.commit()
    
    mainB()
    #sys.exit(0)

    class EventDuck(object):
        def __init__(self, payload):
            self.payload = payload
        def database_payload(self):
            return self.payload

    payloads = pickle.load(open('payloads.pickle','rb'))
    outputs = []
    for p in payloads:
        o2 = []
        outputs.append(o2)
        for payload in p:
            del payload['version']
            o2.append(EventDuck(payload))

    #from sqlalchemy.orm import sessionmaker
    #Session = sessionmaker(engine)
    #with Session() as session:

    with Session(engine) as session:
        try:
            send_to_db(session, outputs)
        except:
            print('Exception in send_to_db:')
            import traceback
            traceback.print_exc()
            sys.exit(0)
        print('Committing session...')
        session.commit()