"""
Setup and pipeline factory for the CHIME testbed.

Used by chord_frb_grpc/frb_sifter_server.py and could be used in load_chime_events.py
or a similar cleaner test pipeline.
"""


def setup():
    from chord_frb_sifter import config
    config.load_actor_configuration()
    config.load_bonsai_config()
    config.load_telescope_config()


def create_pipeline(database_engine=None):
    """Instantiate and return the CHIME test actor pipeline.

    Parameters
    ----------
    database_engine : sqlalchemy Engine, optional
        If None, creates a SQLite engine from CHORD_FRB_DB_URL env var.

    Returns
    -------
    list of (name, actor) tuples
    """
    from chord_frb_sifter import config
    from chord_frb_sifter.actors.beam_buffer import BeamBuffer
    from chord_frb_sifter.actors.beam_grouper import BeamGrouper
    from chord_frb_sifter.actors.event_id_stamper import EventIdStamper
    from chord_frb_sifter.actors.rfi_sifter import RFISifter
    from chord_frb_sifter.actors.bright_pulsar_sifter import BrightPulsarSifter
    from chord_frb_sifter.actors.simple_localizer_cfbm import SimpleLocalizerCFBM
    from chord_frb_sifter.actors.known_source_sifter import KnownSourceSifter
    from chord_frb_sifter.actors.dm_checker import DMChecker
    from chord_frb_sifter.actors.actions import ActionPicker

    if database_engine is None:
        import os
        from chord_frb_db.utils import get_db_engine
        os.environ.setdefault('CHORD_FRB_DB_URL', 'sqlite+pysqlite:///chord_sifter_test.sqlite3')
        database_engine = get_db_engine()

    pipeline = []
    for name, clz in [('BeamBuffer', BeamBuffer),
                      ('BeamGrouper', BeamGrouper),
                      ('EventIdStamper', EventIdStamper),
                      ('RFISifter', RFISifter),
                      ('BrightPulsarSifter', BrightPulsarSifter),
                      ('SimpleLocalizerCFBM', SimpleLocalizerCFBM),
                      ('KnownSourceSifter', KnownSourceSifter),
                      ('DMChecker', DMChecker),
                      ('ActionPicker', ActionPicker)]:
        conf = config.get_worker_configuration(name)
        for key in ['io', 'log', 'use_pickle', 'timeout', 'periodic_update']:
            conf.pop(key, None)
        if clz in (EventIdStamper, KnownSourceSifter, ActionPicker):
            conf['database_engine'] = database_engine
        if clz is SimpleLocalizerCFBM:
            conf = {}
        pipeline.append((name, clz(**conf)))
    return pipeline


def process_events(pipeline, events):
    """Run a list of L1 events through the pipeline. Returns final output events."""
    input_events = [events]
    for name, actor in pipeline:
        output_events = []
        for item in input_events:
            result = actor.perform_action(item)
            if result:
                output_events.extend(r for r in result if r is not None)
        if not output_events:
            break
        input_events = output_events
    return input_events
