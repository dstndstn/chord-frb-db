# List of ToDos for CHORD frb_sifter pipeline actors

The purpose of this document is to compile a list of open tasks, issues, and
a general plan for a complete minimal CHORD FRB sifter pipeline as of June 2026
following the prototype pipeline that runs on dumped CHIME/FRB events.

- Changes necessary to each actor to work with CHORD will be highlighted: Needs 
- Future changes for features beyond the minimal version will be highlighted: Futures 
- Possible issues that *may* need to be resolved will be highlighted (issues 
*have* to be resolved for the minimal pipeline should be Needs): Issues

Example Future features:

- Injections
- Early triggers
- Compatability with CHIME/FRB upgrade

## Infrastruture

### Configuration

In pscholz-dev branch, I have made a config.py module that stores the configuration 
parameters needed by the pipeline. 

Needs:
- injest the upstream config parameter to the module.
- 

### gRPC interface with FRB search

I have a CHIME testbed version of grpc server 
(chord_frb_grpc/frb_sifter_server_chimetest.py, that uses frb_sfiter_chime.proto)
that is probably quite incompatible with the actual pirate one. Some of what is
in that pipeline may be required for the buffering and grouping to work.

Needs:
- review what is needed from CHIME testbed to run with pipeline in the pscholz-dev branch
- update frb_sifter_server.py to be compatible with pipeline
- probably do this last after addressing actor Needs?

### Database

### Actor framework

## Actors

### BeamBuffer

In the current CHIME-event based testbed, there is beam buffering logic in the 
sifter gRPC server. The root of the split is that there are multiple gRPC threads
calling FrbEvents and so need to handle those threads reporting concurrently. 
BeamBuffer is not set up for this.

Needs:
- review what logic is in BeamBuffer and what is in the gRPC server
- remove any duplication. 
- Determine if it all can go in BeamBuffer so we can keep gRPC server simple
- rethink how its threaded? What is an elegant solution? (consult w/ Dustin?)
- can ask Claude for options based on our past brainstorming.

### BeamGrouper

This one should be mostly good to go for CHORD. Some notes:
- My version of it (in contrast to Dustin's) changed to cluster in x, y telescope 
coords instead of beam numbers. This makes it compatible with both CHIME and
CHORD (where beams are not in a simple grid)
- we'll want to settle on coordinates used in the pipeline, I'd advocate for the 
unit-sphere coords, direction cosines, x_tel/y_tel (too many names for these...)
- That will be most relavant for the localizer
- I think the unit-sphere coords are used in the BX-engine to specify beam 
locations, so that would be most natural anyways.
- so may change how spatial clustering is done if coords change.

Issues:
- dead_beams is set as an empty list. How will we track dead beams in CHORD?
- does having the L1 events as dictionary before L2 event creation and as a 
recarray afterwards create future issues for code maintenance. i.e is it fragile 
to future changes from devs that might not understand the distinction.
- what are beam_activity_lookback and dm_activity_lookback? Are they used at all
in the pipeline?

### EventIDStamper

Super simple. Should be fine.

### RFISifter

Needs complete redesign in CHORD? Can we define a minimal one for a v1 Pathfinder
pipeline?

### BrightPulsarSifter

This is a farily simple actor, so should be mostly good to go. All that is 
outstanding is some thought into the list of pulsars.

Needs:
- a list of pulsars given our likely pointing positions should be drawn up.
- check if it is setting the correct flags, fields for the DB (is_known_source etc)

Issues:
- right now the list is hardcoded in the actor code
- the list will change when the CHORD pointing position is changed, do we need
a framework for that?
- known_source_name is set by this actor as well as the KnownSourceSifter. 
Potential for collisions?

Futures:
- I am a bit worried about this when going CHORD -> CHIME upgrade
- The list of pulsars will be much longer for CHIME, is that a problem?

### Localizer

There are three versions in the current sifter repo: 
- SimpleLocalizer: Dustin's version of the simple weighted mean localization. 
- SimpleLocalizerCFBM: My version of the simple weighted mean localization that uses cfbm.
- Localizer: My actual prototype CHORD localizer. Fits a Gaussian to the per beam S/Ns
in a similar fashion to the baseband pipeline.

For CHORD we should get the Localizer one working well.

Needs:
- a CHORD version of cfbm (or some module that handles the needed functionality)
- settle on what coordinates we should use in the pipeline and localize using 
those.
- The fit cannot be performed successfully with one beam. So need to add a fallback
option for that. e.g. a fiducial error given what we would expect if there is only
a single beam detection given the S/N. This is simable. Though also depends on 
subband. Maybe think about how to KISS (otherwise we'll end up with a huge LUT based 
on beam, S/N, and subband!)
- using an analytic Jacobian would make it faster and more robust.
- calculate error from Jacobian (will work much better with analytic Jacobian)

Futures:
- The CHORD Localizer may not work well for the CHIME/FRB upgrade, depending on
the beam density. 

### KnownSourceSifter

Needs:
- replace fixed dm_course_graining_factor=64 to work with CHORD fine grained DMs
- remove sidelobe copy logic? Since not using in CHORD

Futures:
- how will we handle sidelobes in CHIME/FRB upgrade?

Issues:
- the update() method is never called.
- check logic of update() does it actually work?

### DMChecker

### ActionPicker 

## Action picking and execution

## General thoughts on Futures
