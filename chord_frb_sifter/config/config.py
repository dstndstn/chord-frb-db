"""
Store configuration parameters to be used in the chord_sifter pipeline and actors.
"""

# Configs should load in here:
# bonsai (for CHIME), pirate (for CHORD)
# chord_frb_sifter actor configurations
# other telescope parameters? e.g. pointing position
#
# For CHORD, we should get telescope params and pirate config
# from upstream when pipeline starts (L1 should send it to us)
# But for CHIME, comes from files now.

import yaml
from pathlib import Path
from importlib.util import module_from_spec, spec_from_loader
from importlib.machinery import SourceFileLoader

l1_config = {} # bonsai/pirate configs
chord_config = {} # telescope configs
actor_configs = {} # L2/L3 configs


def load_bonsai_config(configfn = 'bonsai_production_fixed_coarse_graining_hybrid_0.8_0.015.txt'):

    path = Path(__file__).parent / configfn

    spec = spec_from_loader("bonsai_cfg", SourceFileLoader("bonsai_cfg", str(path)))
    bonsai_cfg = module_from_spec(spec)
    spec.loader.exec_module(bonsai_cfg)

    global l1_config
    l1_config = bonsai_cfg

# Load upstream config
def load_telescope_config(configfn = 'testChordTelescope.yaml'):

    path = Path(__file__).parent / configfn
    conf = yaml.load(open(path,'r'), Loader=yaml.Loader)

    global chord_config
    chord_config = conf

# from frb_common.pipeline_tools
def load_actor_configuration(configfn = 'drao_epsilon_pipeline_local.yaml'):
    """
    Loads user provided *.yaml configuration file into `config`.

    Parameters
    ----------
    config_file : string
        Name of the configuration file.

    """
    global actor_configs
    config_file = Path(__file__).parent / configfn
    actor_configs = yaml.safe_load(open(config_file))
    is_master.value = config.get("node_type", "MASTER").upper() == "MASTER"

# Load CHIME's L2/L3 worker (actor) configs, will replace with CHORD version.
# For CHORD I don't see why we can't just KISS and load all configs into a 
# single dict and have available to all actors (so no need for this).
def get_worker_configuration(actor_name):
    """
    Extracts module/actor specific parts from `config`.

    Parameters
    ----------
    actor_name : str
        Used as the key to extract configurations dictionary from
        ``config['modules']``

    Returns
    -------
    dict
        A python dictionary containing the parameters used to set up
        both a ``Worker`` instance and its `actor`.

    """
    worker_config = actor_configs.get("generics", {}).copy()
    worker_config.update(actor_configs.get("specifics", {}).get(actor_name, {}))
    return worker_config

