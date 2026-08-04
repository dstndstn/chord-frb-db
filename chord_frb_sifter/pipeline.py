def setup():
    from chord_frb_sifter import config
    config.load_actor_configuration()
    config.load_bonsai_config()
    config.load_telescope_config()
                
# These are our simplified CHORD pipeline actors.
# A "pipeline" here is just a list of actors.
def simple_create_pipeline(database_engine):
    # Still reusing some of the config stuff... can probably simplify this too!!
    from frb_common import pipeline_tools

    from chord_frb_sifter.actors.beam_buffer import BeamBuffer
    from chord_frb_sifter.actors.beam_grouper import BeamGrouper
    from chord_frb_sifter.actors.localizer import Localizer
    from chord_frb_sifter.actors.simple_localizer import SimpleLocalizer
    from chord_frb_sifter.actors.bright_pulsar_sifter import BrightPulsarSifter
    from chord_frb_sifter.actors.rfi_sifter import RFISifter
    from chord_frb_sifter.actors.dm_checker import DMChecker
    #from chord_frb_sifter.actors.known_source import KnownSourceSifter
    from chord_frb_sifter.actors.actions import ActionPicker
    from chord_frb_sifter.actors.event_id_stamper import EventIdStamper

    pipeline = []
    for name,clz in [('BeamBuffer', BeamBuffer),
                     ('BeamGrouper', BeamGrouper),
                     ('EventIdStamper', EventIdStamper),
                     ('RFISifter', RFISifter),
                     ("BrightPulsarSifter", BrightPulsarSifter),
                     ('Localizer', Localizer), # Gauss2D localizer
                     #('Localizer', SimpleLocalizer), # S/N weighted
                     #('KnownSourceSifter', KnownSourceSifter),
                     ('DMChecker', DMChecker),
                     # ('FluxEstimator', FluxEstimator),
                     ('ActionPicker', ActionPicker),
                     ]:
        conf = pipeline_tools.get_worker_configuration(name)
        conf.pop('io')
        conf.pop('log')
        picl = conf.pop('use_pickle')
        conf.pop('timeout')
        conf.pop('periodic_update')
        conf.update(database_engine=database_engine)
        p = clz(**conf)
        pipeline.append(p)
    return pipeline

# Fires a list of events through the pipeline.
def simple_process_events(pipeline, events):
    input_events = [events]
    output_events = []

    # This the famed "It's just a FOR loop" framework
    for actor in pipeline:
        output_events = []
        print('Actor', actor, ': feeding %i events' % len(input_events))
        for in_item in input_events:
            items = actor.perform_action(in_item)
            print('Actor', actor, 'in event', in_item, '-> out events', items)
            if items is None:
                continue
            for item in items:
                if item is None:
                    continue
                output_events.append(item)
        print('Actor', actor, ': produced %i events' % len(output_events))
        if len(output_events) == 0:
            break
        input_events = output_events
    return output_events
