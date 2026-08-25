from chord_frb_sifter.actors import Actor
from chord_frb_sifter.event import L1Event, L2Event

from chord_frb_db.utils import get_db_engine
from sqlalchemy.orm import Session

from queue import Queue
from threading import Thread

import numpy as np

import concurrent.futures as cf

# Should the database stuff be in a separate actor?

# Returns dispersion delay in seconds
# The 'DM' parameter is the dispersion measure in its standard units (pc cm^{-3})
# freq is in MHz.
# This was lifted from https://github.com/kmsmith137/simpulse/blob/master/simpulse.hpp#L32
def dispersion_delay(dm, freq_MHz):
    return 4.148806e3 * dm / (freq_MHz * freq_MHz)

class ActionPicker(Actor):
    def __init__(self, database_engine=None, sifter=None, **kwargs):
        super().__init__(**kwargs)
        self.sifter = sifter
        self.db_queue = Queue()
        self.db_thread = Thread(target=ActionPicker.run_db, args=(self, database_engine))
        self.db_thread.start()
        #self.intensity_queue = Queue()
        #self.intensity_thread = Thread(target=ActionPicker.run_intensity,
        #                               args=(self,))
        #self.intensity_thread.start()
        #self.db_executor = cf.ThreadPoolExecutor(max_workers=3)
        self.intensity_executor = cf.ThreadPoolExecutor(max_workers=10)
        self.intensity_futures = []

    def __str__(self):
        return 'ActionPicker'

    def shutdown(self):
        #self.db_executor.shutdown(wait=True)
        print('Shutting down ActionPicker... sending None on db queue')
        self.db_queue.put(None)
        #self.intensity_queue.put(None)
        print('Joining db thread')
        self.db_thread.join()
        #print('Joining intensity callback thread')
        #self.intensity_thread.join()
        print('Shutting down intensity callback thread pool...')
        self.intensity_executor.shutdown(wait=True)
        print('Shutdown of intensity callback thread pool finished')
        print('done shutdown of ActionPicker')

    def _perform_action(self, event_group):
        for event in event_group.events:
            # Log everything in db?
            self.save_to_db(event)

            # Intensity callback
            if event.is_frb() or event.is_ambiguous():
                print('FRB or Ambiguous event -- sending intensity callback!')
                self.send_intensity_callback(event)
            # if event.is_rfi():
            #     continue
        return [event_group]

    def save_to_db(self, event):
        # FIXME -- put_nowait ? queue size? timeout?
        #print('Saving event to db:', event)
        self.db_queue.put(('event', event))

    def send_intensity_callback(self, event):
        #self.intensity_queue.put(event)
        future = self.intensity_executor.submit(ActionPicker.intensity_callback, self, event)
        print('future:', future)
        try:
            e_immediate = future.exception(timeout=0)
            if e_immediate is not None:
                raise e_immediate
        except TimeoutError:
            pass
        self.intensity_futures.append(future)

    # There's no real reason this needs to be a class method...
    def run_db(self, database_engine):
        from chord_frb_db.models import IntensityFile
        import sqlalchemy as sa
        print('Starting database interaction thread.')
        with Session(database_engine) as session:
            while True:
                try:
                    print('Waiting for event from db queue.  Approx size: %i' % self.db_queue.qsize())
                    req = self.db_queue.get()
                    if req is None:
                        break
                    (req_type, arg) = req
                    if req_type == 'event':
                        event = arg
                        self.save_event_to_db(session, event)
                        session.flush()
                        session.commit()
                    # elif req_type == 'intensity_files':
                    #     event_id, beams, fpga_start, fpga_end, acqdir, filenames = arg
                    #     # List could be empty... do we want to record the fact that we tried a callback?
                    #     print('Recording in db: intensity files for event %i: [ %s ]' % (event_id, ', '.join(filenames)))
                    #     for fn in filenames:
                    #         # get or create
                    #         ifile = session.execute(sa.select(IntensityFile)
                    #                                 .where(IntensityFile.filename==fn)
                    #                                 ).one_or_none()
                    #         if ifile is None:
                    #             ifile = IntensityFile(filename=fn,
                    #                                   succeeded=False,
                    #                                   error_message='',
                    #                                   event_id=event_id)
                    #             print('Created IntensityFile db entry: event %i, file %s' % (event_id, fn))
                    #             session.add(ifile)
                    #         else:
                    #             ifile.event_id = event_id
                    #             print('Updated IntensityFile db entry: set event = %i for file %s' % (event_id, fn))
                    #         session.flush()
                    #     session.commit()

                except Exception as e:
                    print('Database thread hit exception:', e)
                    import traceback
                    traceback.print_exc()
                    raise e
        print('Database thread ending')

    def save_event_to_db(self, session, event):
        from chord_frb_db.models import EventBeam, Event

        # Save L1 events
        l1_events = event.get('l1_events', [])
        l1_db_objs = []
        l1_payload = [e.database_payload() for e in l1_events]
        for args in l1_payload:
            print('L1 event db from:', args)
            db_obj = EventBeam(**args)
            session.add(db_obj)
            session.flush()
            # Now we know the L1 event's unique id
            assert(db_obj.id is not None)
            l1_db_objs.append(db_obj)

        # Save L2 event
        l2_payload = event.database_payload()
        l2_db_obj = Event(**l2_payload)
        # Add L2 event to db
        session.add(l2_db_obj)

        # Now we can associate the L1 events with the L2 event.
        for e in l1_db_objs:
            l2_db_obj.beams.append(e)
        # DEBUG
        session.flush()
        print('Saved L2 event id', l2_db_obj.event_id)

    # # There's no real reason this needs to be a class method...
    # def run_intensity(self):
    #     print('Starting intensity callback thread.')
    #     while True:
    #         print('Waiting for event from intensity queue.  Approx size: %i' %
    #               self.intensity_queue.qsize())
    #         event = self.intensity_queue.get()
    #         if event is None:
    #             break
    #         self.intensity_callback(event)
    #     print('Intensity callback thread ending')

    def intensity_callback(self, event):
        print('Intensity callback: event', event)#event_id', event.event_id)

        # gather all beams that triggered for this grouped event.
        # FIXME -- add adjacent beams?

        beams = set([event.beam_id])
        for e in event.l1_events:
            beams.add(e['beam_id'])
        beams = list(beams)
        print('All triggered beams:', beams)

        from chord_frb_grpc.frb_search_pb2 import WriteFilesRequest, SubscribeFilesRequest

        beamset_beams = {}
        for beam in beams:
            beamset = self.sifter.beam_id_to_beamset[beam]
            if not beamset in beamset_beams:
                beamset_beams[beamset] = []
            beamset_beams[beamset].append(beam)

        ns_per_fpga = self.sifter.nanosec_per_fpga_seq()
        fpga_buffer = int(1e9 / ns_per_fpga)
        # the event's FPGA_TIMESTAMP is the arrival time at the bottom of the frequency band.
        fpga_end = event.fpga_timestamp + fpga_buffer
        freq_lo, freq_hi = self.sifter.get_freq_range()
        dt_lo = dispersion_delay(event.dm, freq_lo)
        dt_hi = dispersion_delay(event.dm, freq_hi)
        print('DM %.1f: delay at %f MHz is %.3f sec' % (event.dm, freq_lo, dt_lo))
        print('DM %.1f: delay at %f MHz is %.3f sec' % (event.dm, freq_hi, dt_hi))
        dt = dt_lo - dt_hi
        assert(dt > 0)
        dfpga = int(1e9 * dt / ns_per_fpga)
        fpga_start = event.fpga_timestamp - dfpga - fpga_buffer
        print('FPGA range requested: %i, %i' % (fpga_start, fpga_end))

        for beamset,beams in beamset_beams.items():
            (addr, stub) = self.sifter.beamset_pirate_rpc[beamset]
            print('Sending intensity callback to pirate RPC address:', addr, 'using stub', stub)
            acqdir = 'event-%08i' % event.event_id
            req = WriteFilesRequest(protocol_version = 2,
                                    beams = beams,
                                    fpga_seq_start = fpga_start,
                                    fpga_seq_end = fpga_end,
                                    acqdir = acqdir)
            print('Sending WriteFilesRequest:', req)
            resp = stub.WriteFiles(req)
            print('Got WriteFiles response:', resp)

            # FIXME -- record these filenames in the database...?
            for filename in resp.filename_list:
                print('Pirate will write file %s' % filename)

            #self.db_queue.put(('intensity_files', (event.event_id, beams, fpga_start, fpga_end,
            #                                       acqdir, resp.filename_list)))
            for fn in resp.filename_list:
                self.sifter.file_update_queue.put((event.event_id, fn, None))

            #req = SubscribeFilesRequest
            #resp = stub.SubscribeFiles(req)

        # example WriteFilesResponse:
        # Got WriteFiles response: filename_list: "event-00003716/frame_b11_t113.asdf"
        #filename_list: "event-00003716/frame_b11_t114.asdf"
        #filename_list: "event-00003716/frame_b11_t115.asdf"
        #filename_list: "event-00003716/frame_b11_t116.asdf"
        #filename_list: "event-00003716/frame_b11_t117.asdf"
        # ...
            
        # example event data we have at this point:
        # {'beam_id': 8, 'fpga_timestamp': 5989620, 'dm': 25.25835418701172, 'rfi_prob': 0.0, 'width_ms': 0.9983999729156494, 'subband_freq_lo_MHz': 400.0, 'subband_freq_hi_MHz': 800.0, 'is_fake': False, 'rfi_grade_level1': 10.0, 'chunk_fpga_start': 5940480, 'chunk_utc': 1786482556.8862808, 'timestamp_utc': 1786482557.1378777, 'is_incoherent': False, 'tree_index': 0, 'dm_error': 0.1, 'pipeline_timestamp': 1712085.576748714, 'pipeline_id': 1, 'max_beam_grid_x': -0.1, 'max_beam_grid_y': 0.033333333333333326, 'max_snr': 25.013864517211914, 'beam_activity': 2, 'dm_activity': 2, 'beam_activity_lookback': deque([0, 0, 0, 0, 0, 0, 0, 0, 0, 2], maxlen=10), 'dm_activity_lookback': deque([0, 0, 0, 0, 0, 0, 0, 0, 0, 2], maxlen=10), 'avg_l1_grade': 10.0, 'n_live_beams': 16, 'l1_events': [{'beam_id': 8, 'fpga_timestamp': 5989620, 'dm': 25.25835418701172, 'snr': 25.013864517211914, 'rfi_prob': 0.0, 'width_ms': 0.9983999729156494, 'subband_freq_lo_MHz': 400.0, 'subband_freq_hi_MHz': 800.0, 'is_fake': False, 'rfi_grade_level1': 10.0, 'beam_grid_x': -0.1, 'beam_grid_y': 0.033333333333333326, 'chunk_fpga_start': 5940480, 'chunk_utc': 1786482556.8862808, 'timestamp_utc': 1786482557.1378777, 'is_incoherent': False, 'tree_index': 0, 'dm_error': 0.1, 'pipeline_timestamp': 1712085.576748714, 'pipeline_id': 1, 'id': 3621}], 'event_id': 3622, 'rfi_grade_level2': 9.996442488679584, 'rfi_grade_metrics_level2': {'ML_Classifier_grade': 0.9996442488679583}, 'is_rfi': False, 'is_bright_pulsar': False, 'ra': 348.80541191130703, 'dec': -4.1414448711052705, 'ra_err': nan, 'dec_err': nan, 'flag_ambiguous': True, 'dm_gal_ymw_2016_max': 23.48247156629519, 'dm_gal_ne_2001_max': 32.893106974458235}
        
