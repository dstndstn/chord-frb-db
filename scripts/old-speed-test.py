## Old code running a speed test on a simple "for-loop" framework vs CHIME's L2/L3
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
