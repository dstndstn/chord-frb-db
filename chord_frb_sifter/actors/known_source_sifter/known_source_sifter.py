"""The CHIME/FRB L2/L3 Known Source Sifter contains an actor styled
class that determines if an event is likely originating from a known
source.

"""


import shutil
from time import sleep
import time
from os import path
import requests
import numpy as np
import prometheus_client as prom
from frb_common import ActorBaseClass
from . import known_source_filters
from frb_L2_L3 import config_dir

__author__ = "CHIME FRB Group"
__version__ = "0.1"
__maintainer__ = "Ziggy Pleunis"
__developers__ = "Ziggy Pleunis"
__email__ = "ziggy@physics.mcgill.ca"
__status__ = "Beta"


class KnownSourceSifter(ActorBaseClass):
    """A subclass of `ActorBaseClass` that determines if an L2 event
    matches a known source, based on sky location and dispersion
    measure.

    Parameters
    ----------
    **kwargs : dict, optional
        Additional parameters are used to initialize superclass
        (``ActorBaseClass``).

    """

    EVENT_CLASS = prom.Counter(
        "frb_kssifter_event_total",
        "Number of events classified by the KnownSourceSifter as a particular type",
        ["type", "worker"],
    )

    def __init__(self, threshold, sky_region, dm_region, filters, **kwargs):

        super(KnownSourceSifter, self).__init__(**kwargs)

        self.threshold = threshold
        self.sky_region = sky_region
        self.dm_region = dm_region
        self.filters = filters

        self.config_init = False
        self.ks_database = []
        self.ks_filter_names = []
        self.ks_filter_weights = []

        self.load_filters()
        self.ks_url = "http://frb-l4:8100/known_sources/api/deploy_database/"
        #sleep(1 + self.worker_id*1.5)
        print("loading KSS into ",config_dir + "/data/known_source_sifter/")
        self.retry_load_ks_database(config_dir + "/data/known_source_sifter/")
        self.logger.info("Loading in the known sources database....")

    def retry_load_ks_database(self, fpath):
        for i in range(5):
            try:
                print("try KSS load",i)
                self.load_ks_database(fpath=fpath)
                break
            except Exception as e:
                if i == 4:
                    raise(e)
                time.sleep(0.1)

    def shutdown(self):
        self.logger.info("I have shut down gracefully")

    def update(self):
        """Reload the known sources database periodically."""
        self.logger.info("Reloading known sources database")
        self.retry_load_ks_database(config_dir + "/data/known_source_sifter/")

    def perform_action(self, event):
        """Pipeline function that compares `event` with known sources
        in the known sources database.

        The function queries the known source database to retrieve all
        known sources within a position and dispersion measure range
        determined by `sky_region` and `dm_region` in the KS sifter
        configuration file. The sky position and dispersion measure of
        the event and the known sources are then compared using some
        statistic, using the function calculate_response.

        Parameters
        ----------
        event : class
            Class should be ``L2Event``.

        Returns
        -------
        list of one ``L2Event``
            If the L2 event matched a known source, `known_source` is
            set to True and `known_source_name` to the name of the known
            source in the known sources database.

        """
        try:
            if self.pipeline_mode == "PASS_THROUGH":
                event.pipeline_mode[self.process_name] = 0
                from copy import copy

                event_copy = copy(event)
            elif self.pipeline_mode == "DEBUG":
                event.pipeline_mode[self.process_name] = 1
            elif self.pipeline_mode == "SCIENCE":
                event.pipeline_mode[self.process_name] = 2

            if np.in1d(event.l1_events["beam_no"],
                       self.incoherent_beam_ids).all():
                self.logger.debug("Event detected in incoherent beam, " +
                                  "will only compare RA, not Dec")

                ks_region, _ = nearby_known_sources_window(self.ks_database,
                    event.pos_ra_deg, event.dm, self.sky_region,
                    event.dm_error * self.dm_region)
            else:
                ks_region, _ = nearby_known_sources_circle(
                    self.ks_database,
                    event.pos_ra_deg,
                    event.pos_dec_deg,
                    event.dm,
                    self.sky_region,
                    event.dm_error * self.dm_region,
                )

            self.logger.debug('Comparing event with ' +
                              '{0} '.format(len(ks_region)) +
                              'known sources')

            # only perform the comparison if there is something to compare with
            if ks_region.size > 0:
                self.logger.debug(
                    "Known source names: " + "{0}".format(ks_region["source_name"])
                )

                probability = self.calculate_response(event, ks_region)

                probability_max = np.nanmax(probability)
                self.logger.debug(
                    "Probability: " + "{0}".format(probability)
                )

                # does the most likely association meet the assoc. threshold?
                if probability_max > self.threshold:
                    best_match = ks_region[np.argmax(probability)]

                    # find the ID of the known source in the KS database
                    source_name = best_match["source_name"]

                    # remove the side-lobe copy identifier, if present
                    if "_" in source_name:
                        source_name = source_name.split("_")[0]
                        src_mask = np.where(self.ks_database["source_name"] == source_name)[0]
                        event.futures.known_source_pos_ra_deg = self.ks_database[src_mask]['pos_ra_deg'][0]
                        event.futures.known_source_pos_dec_deg = self.ks_database[src_mask]['pos_dec_deg'][0]
                    else:
                        event.futures.known_source_pos_ra_deg = best_match["pos_ra_deg"]
                        event.futures.known_source_pos_dec_deg = best_match["pos_dec_deg"]
                     
                    event.known_source_name = source_name

                    event.known_source_rating = probability_max

                    # set true DM, RA, Dec
                    event.futures.known_source_dm = best_match["dm"]
                     
                    # set maximum expected Galactic DM in event header
                    event.dm_gal_ne_2001_max = best_match[
                        "dm_galactic_ne_2001_max"
                    ]
                    event.dm_gal_ymw_2016_max = best_match[
                        "dm_galactic_ymw_2016_max"
                    ]

                    # i.e., save known source metrics but do not override
                    # `event_category` for RFI events
                    if event.event_category != 3:
                        # associate known source
                        event.event_category = 2
                        self.logger.debug(
                            "Event is associated with known "
                            + "source {0}".format(source_name)
                        )
                        # count the number of known source associations
                        self.EVENT_CLASS.labels(
                            type="known_source", worker=self.worker_id
                        ).inc()
                else:
                    if event.event_category != 3:
                        # unknown source
                        event.event_category = 1
                        self.EVENT_CLASS.labels(
                            type="unknown_source", worker=self.worker_id
                        ).inc()
            else:
                if event.event_category != 3:
                    # unknown source
                    event.event_category = 1
                    self.EVENT_CLASS.labels(
                        type="unknown_source", worker=self.worker_id
                    ).inc()

            if self.pipeline_mode == "PASS_THROUGH":
                event_copy.event_status[self.process_name] = 3  # bypass
                self.PROCESS_STATUS.labels(
                    status="success", actor=self.process_name
                ).inc()
                return [event_copy]
            else:
                event.event_status[self.process_name] = 0  # succes
                # count the number of successes
                self.PROCESS_STATUS.labels(
                    status="success", actor=self.process_name
                ).inc()
                return [event]

        except Exception as e:
            import traceback;traceback.print_exc()
            

            event.event_status[self.process_name] = 2  # failure
            # count the number of failures
            self.PROCESS_STATUS.labels(status="failure", actor=self.process_name).inc()
            return [event]

    def load_filters(self):
        """Initializes the filters defined in the configuration file.

        Function appends to `ks_filter_names` and `ks_filter_weights`.

        """
        # set sifter threshold
        try:
            self.threshold = float(self.threshold)
            self.logger.info("Setting threshold to " + "{0}".format(self.threshold))
        except Exception as e:
            self.logger.critical(e)
            self.logger.critical(
                "Unable to load. "
                + "Setting threshold to "
                + "{0}".format(self.threshold)
            )

        # initialize filters
        for filt in self.filters:
            # check if this filter definition exists
            if hasattr(known_source_filters, filt[0]):
                self.ks_filter_names.append(filt[0])
                self.ks_filter_weights.append(float(filt[1]))
                self.logger.info("Filter '{0}' loaded".format(filt[0]))
            else:
                self.logger.critical(
                    "Filter '{0}' ".format(filt[0])
                    + "is not defined in "
                    + "known_source_filters.py!"
                )

        nof = len(self.ks_filter_names)
        if nof:
            self.logger.info("Read {nof} filters".format(nof=nof))
        else:
            self.logger.critical(
                "There are no filters defined! "
                + "No known sources will be recognized!"
            )
        self.config_init = True

    def load_ks_database(self, fpath="./", fname="ks_database.npy"):
        """Load known sources database. It's currently a numpy file.

        Parameters
        ----------
        fpath : str
            path to the known source database.

        fname : str
            Name of the known source database.
            (Default: ks_database.npy)

        """
        db = path.join(fpath, fname)
        self.ks_database = np.load(db)
        # Download the file so that the next time, they all update to the same db
        if self.worker_id == 0:
            self.logger.info(f"WORKER IS {self.worker_id}. Downloading file")
            try:
                download_file(self.ks_url, db+".tmp", self.logger)
                shutil.move(db + ".tmp", db)
                self.logger.info(
                    "{ks_no} known sources loaded".format(ks_no=self.ks_database.size)
                )
            except Exception as e:
                self.logger.warn("Unable to reload ks db. Continuing to use existing one.  " + str(e))
            
    def calculate_response(self, event, ks_region):
        """Calculates statistical match of an L2 event to a list of
        known sources.

        Function loops over the filters listed in the KS sifter
        configuration file and defined in the known_source_filters.py script.

        Parameters
        ----------
        event : class
            Class should be ``L2Event``.

        ks_region : array_like
            List containing known sources in the neighborhood of
            event.

        Returns
        -------
        probability : float, array
            An array with the probabilities representing the
            likelihoods that the event is associated with neighbouring
            known sources.

        """
        assert self.config_init

        # call the filters one-by-one
        for i, filt in enumerate(self.ks_filter_names):
            # get the function call
            function = getattr(known_source_filters, filt)
            # function adds the grade to the object header
            if i == 0:
                bayes_factor = self.ks_filter_weights[i] * function(
                    event,
                    ks_region,
                    self.ks_filter_weights[i],
                    incoherent_beam_ids=self.incoherent_beam_ids,
                )
            else:
                # Btot = B1 * B2 * ... * Bn
                bayes_factor *= self.ks_filter_weights[i] * function(
                    event,
                    ks_region,
                    self.ks_filter_weights[i],
                    incoherent_beam_ids=self.incoherent_beam_ids,
                )

        # get unique number of known sources (i.e., do not double count copies)
        ks_names = []
        for ks_name in ks_region["source_name"]:
            ks_names.append(ks_name.split("_")[0])
        n_sources = np.unique(ks_names).size

        # calculate posterior probability
        prior = 1. / n_sources
        probability = bayes_factor * prior / (1 + bayes_factor * prior)

        return probability


def nearby_known_sources_circle(
    ks_database, pos_ra_deg, pos_dec_deg, dm, radius, delta_dm
):
    """Retrieve known sources with angular separation less than
    `radius` of the provided coordinates and with DM less than
    `delta_dm` away from the provided DM.

    Parameters
    ----------
    ks_database : array_like
        CHIME/FRB known sources database.
    pos_ra_deg : float
        Right ascension of the center of the circle, in degrees.
    pos_dec_deg : float
        Declination of the center of the circle, in degrees.
    dm : float
        Dispersion measure of the search, in pc cm-3.
    radius : float
        Maximum angular separation of sources to consider.
    delta_dm : float
        Maximum DM separatio of the sources to consider.

    Returns
    -------
    ks_region : array_like
        Part of the known sources database.
    separation : array_like
        Angular separation to source to consider, in degrees.

    """
    # select on DMs
    dm_mask = np.where(np.abs(ks_database["dm"] - dm) < delta_dm)[0]

    if dm_mask.size > 0:
        # select on angular separation
        _, separation = known_source_filters.angular_separation(
            ks_database[dm_mask]['pos_ra_deg'],
            ks_database[dm_mask]['pos_dec_deg'],
            pos_ra_deg, pos_dec_deg)

        sky_mask = np.where(separation < radius)[0]

        if sky_mask.size > 0:
            # sort on angular separation
            sorted_idx = separation[sky_mask].argsort()

            return (
                ks_database[dm_mask[sky_mask[sorted_idx]]],
                separation[sky_mask[sorted_idx]],
            )

    return np.array([]), np.array([])


def nearby_known_sources_window(ks_database, pos_ra_deg, dm, delta_ra, delta_dm):
    """Retrieve known sources with RA less than `delta_ra` away from
    the provided RA and with DM less than `delta_dm` away from the
    provided DM.

    Parameters
    ----------
    ks_database : array_like
        CHIME/FRB known sources database.
    pos_ra_deg : float
        Right ascension of the center of the circle, in degrees.
    pos_dec_deg : float
        Declination of the center of the circle, in degrees.
    dm : float
        Dispersion measure of the search, in pc cm-3.
    delta_ra : float
        Maximum angular separation of sources to consider.
    delta_dm : float
        Maximum DM separatio of the sources to consider.

    Returns
    -------
    ks_region : array_like
        Part of the known sources database.
    separation : array_like
        Angular separation to source to consider, in degrees.

    """
    # select on DMs
    dm_mask = np.where(np.abs(ks_database["dm"] - dm) < delta_dm)[0]

    if dm_mask.size > 0:
        # select on separation in RA
        separation = np.abs((ks_database[dm_mask]["pos_ra_deg"] - pos_ra_deg) % 360.0)
        sky_mask = np.where(separation < delta_ra)[0]

        if sky_mask.size > 0:
            # sort on separation in RA
            sorted_idx = separation[sky_mask].argsort()

            return (
                ks_database[dm_mask[sky_mask[sorted_idx]]],
                separation[sky_mask[sorted_idx]],
            )

    return np.array([]), np.array([])

def download_file(url, local_filename, logger):
    """Downloads the known source database."""
    logger.info(f"Downloading from {url} to file {local_filename}")
    # Attempt 10 times
    for i in range(10):
        try:
            logger.info(f"Downloading from {url}")
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                logger.info(f"Downloading to {local_filename}")
                with open(local_filename, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
                    break
        except Exception as e:
            if i == 9:
                raise(e)
            sleep(0.1)
     
if __name__ == "__main__":

    """
    from frb_common.events import simulate_events

    sim = simulate_events.SimulateEvents()

    ks_sifter = KnownSourceSifter(
        threshold=1.0,
        sky_region=5.0,
        dm_region=2.0,
        filters=[["compare_position", 1.0], ["compare_dm", 1.0]],
        pipeline_mode="DEBUG",
    )

    # TODO method in `frb_common` is currently broken
    revents = sim.get_l3_events(number_of_events=10)

    ks_sifter.perform_action(revents)
    """

    # TODO can probably reduce `sky_region`
    ks_sifter = KnownSourceSifter(threshold=1.0, sky_region=5.0, dm_region=2.0,
                                  filters=[['compare_position', 1.0],
                                           ['compare_dm', 1.0]],
                                  pipeline_mode='DEBUG',
                                  incoherent_beam_ids = \
                                  np.array([0, 1000, 2000, 3000]))

    events = np.load("B0329_events.npy", allow_pickle=True, encoding="latin1")

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(2, sharex=True, gridspec_kw={"hspace": 0,
                           "height_ratios": [1, 4]})

    for event in events:
        #if not np.in1d(event.l1_events["beam_no"],
        #               np.array([0])).all():
        #    continue
        event.known_source_name = ""
        event.known_source_rating = -1

        processed_event = ks_sifter.perform_action(event)[0]

        if processed_event.known_source_name == "B0329+54":
            color = "tab:blue"
        else:
            color = "tab:gray"

        ax[0].scatter(processed_event.pos_ra_deg,
            processed_event.known_source_rating, color=color, marker=".")

        ax[1].errorbar(processed_event.pos_ra_deg, processed_event.pos_dec_deg,
                       xerr=processed_event.pos_error_semiminor_deg_68,
                       yerr=processed_event.pos_error_semimajor_deg_68,
                       color=color, marker=".")

    # TODO add all known_sources in neighborhood in the figure

    ax[0].set_ylabel("Probability")
    ax[1].set_xlabel("RA (deg)")
    ax[1].set_ylabel("Dec (deg)")

    plt.savefig("test_results.png", dpi=150)
