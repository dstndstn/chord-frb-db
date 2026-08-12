from chord_frb_sifter.actors import Actor
from chord_frb_sifter.event import L1Event, L2Event

from chord_frb_db.utils import get_db_engine
from sqlalchemy.orm import Session

from queue import Queue
from threading import Thread

import numpy as np

import concurrent.futures as cf

# Should the database stuff be in a separate actor?

class ActionPicker(Actor):
    def __init__(self, database_engine=None, **kwargs):
        super().__init__(**kwargs)
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
        self.db_queue.put(event)

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
        print('Starting database interaction thread.')
        with Session(database_engine) as session:
            while True:
                try:
                    print('Waiting for event from db queue.  Approx size: %i' % self.db_queue.qsize())
                    event = self.db_queue.get()
                    if event is None:
                        break
                    self.save_event_to_db(session, event)
                    session.flush()
                    session.commit()
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

        # example event data we have at this point:
        # {'beam_id': 8, 'fpga_timestamp': 5989620, 'dm': 25.25835418701172, 'rfi_prob': 0.0, 'width_ms': 0.9983999729156494, 'subband_freq_lo_MHz': 400.0, 'subband_freq_hi_MHz': 800.0, 'is_fake': False, 'rfi_grade_level1': 10.0, 'chunk_fpga_start': 5940480, 'chunk_utc': 1786482556.8862808, 'timestamp_utc': 1786482557.1378777, 'is_incoherent': False, 'tree_index': 0, 'dm_error': 0.1, 'pipeline_timestamp': 1712085.576748714, 'pipeline_id': 1, 'max_beam_grid_x': -0.1, 'max_beam_grid_y': 0.033333333333333326, 'max_snr': 25.013864517211914, 'beam_activity': 2, 'dm_activity': 2, 'beam_activity_lookback': deque([0, 0, 0, 0, 0, 0, 0, 0, 0, 2], maxlen=10), 'dm_activity_lookback': deque([0, 0, 0, 0, 0, 0, 0, 0, 0, 2], maxlen=10), 'avg_l1_grade': 10.0, 'n_live_beams': 16, 'l1_events': [{'beam_id': 8, 'fpga_timestamp': 5989620, 'dm': 25.25835418701172, 'snr': 25.013864517211914, 'rfi_prob': 0.0, 'width_ms': 0.9983999729156494, 'subband_freq_lo_MHz': 400.0, 'subband_freq_hi_MHz': 800.0, 'is_fake': False, 'rfi_grade_level1': 10.0, 'beam_grid_x': -0.1, 'beam_grid_y': 0.033333333333333326, 'chunk_fpga_start': 5940480, 'chunk_utc': 1786482556.8862808, 'timestamp_utc': 1786482557.1378777, 'is_incoherent': False, 'tree_index': 0, 'dm_error': 0.1, 'pipeline_timestamp': 1712085.576748714, 'pipeline_id': 1, 'id': 3621}], 'event_id': 3622, 'rfi_grade_level2': 9.996442488679584, 'rfi_grade_metrics_level2': {'ML_Classifier_grade': 0.9996442488679583}, 'is_rfi': False, 'is_bright_pulsar': False, 'ra': 348.80541191130703, 'dec': -4.1414448711052705, 'ra_err': nan, 'dec_err': nan, 'flag_ambiguous': True, 'dm_gal_ymw_2016_max': 23.48247156629519, 'dm_gal_ne_2001_max': 32.893106974458235}
        
