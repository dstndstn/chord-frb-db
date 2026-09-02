
def setup():
    from frb_common import pipeline_tools
    from frb_common.events import L1Event
    import importlib.resources
    # all pipeline behaviour is encoded in config file
    configfn = 'drao_epsilon_pipeline_local.yaml'
    config = importlib.resources.files('chord_frb_sifter.config').joinpath(configfn)
    with importlib.resources.as_file(config) as config_path:
        pipeline_tools.load_configuration(config_path)
    bonsai_config = pipeline_tools.config["generics"]["bonsai_config"]
    L1Event.use_bonsai_config(bonsai_config)
                
# These are our simplified CHORD pipeline actors.
# A "pipeline" here is just a list of actors.
def simple_create_pipeline(database_engine, **kwargs):
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
        conf.update(kwargs)
        p = clz(**conf)
        pipeline.append(p)
    return pipeline

# Fires a list of events through the pipeline.
def simple_process_events(pipeline, event_group):
    input_groups = [event_group]
    output_groups = []

    # This the famed "It's just a FOR loop" framework
    for actor in pipeline:
        print('Actor', actor, ': feeding %i groups of events' % len(input_groups))
        output_groups = []
        for event_group in input_groups:
            print('Actor', actor, 'sending input group', event_group)
            groups = actor.perform_action(event_group)
            print('Actor', actor, 'input group', event_group, '-> output groups', groups)
            if groups is None:
                continue
            for group in groups:
                if group is None:
                    continue
                output_groups.append(group)
        print('Actor', actor, ': produced %i groups' % len(output_groups))
        if len(output_groups) == 0:
            break
        input_groups = output_groups
    return output_groups
