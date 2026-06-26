"""
CHORD prototype based on the CHIME/FRB L2/L3 Known Source Sifter.

Contains an actor styled class that determines if an event is likely 
originating from a known source.

"""


import concurrent.futures as cf
import numpy as np
from chord_frb_sifter.actors import Actor
from . import known_source_filters

_KS_DTYPE = np.dtype([
    ('id',          np.int64),
    ('source_name', 'U64'),
    ('pos_ra_deg',  np.float32),
    ('pos_dec_deg', np.float32),
    ('dm',          np.float32),
])


def _load_known_sources(database_engine):
    """Query all KnownSource rows and return as a numpy recarray."""
    from chord_frb_db.models import KnownSource
    from sqlalchemy.orm import Session
    from sqlalchemy import select

    rows = []
    with Session(database_engine) as session:
        for (ks,) in session.execute(select(KnownSource)):
            rows.append((ks.id, ks.name, ks.ra, ks.dec, ks.dm))

    if not rows:
        return np.zeros(0, dtype=_KS_DTYPE)

    arr = np.array(rows, dtype=_KS_DTYPE)
    print('KnownSourceSifter: loaded %d known sources from DB' % len(arr))
    return arr


class KnownSourceSifter(Actor):
    """A subclass of `Actor` that determines if an L2 event
    matches a known source, based on sky location and dispersion
    measure.

    Parameters
    ----------
    database_engine : sqlalchemy Engine
        Used to load and periodically refresh the known source catalog.
    incoherent_beam_ids : list, optional
        Beam IDs considered incoherent (RA-only position comparison).
        Defaults to [0, 1000, 2000, 3000].
    **kwargs : dict, optional
        Additional parameters are passed to the superclass (``Actor``).

    """

    def __init__(self, threshold, sky_region, dm_region, filters,
                 database_engine=None, incoherent_beam_ids=None, **kwargs):

        super(KnownSourceSifter, self).__init__(**kwargs)

        self.incoherent_beam_ids = incoherent_beam_ids if incoherent_beam_ids is not None else [0, 1000, 2000, 3000]

        self.threshold = threshold
        self.sky_region = sky_region
        self.dm_region = dm_region
        self.filters = filters
        self.database_engine = database_engine

        self.ks_database = []
        self.ks_filter_names = []
        self.ks_filter_weights = []

        self.load_filters()
        self.ks_database = _load_known_sources(database_engine)
        self._executor = cf.ThreadPoolExecutor(max_workers=1)
        self._update_future = None

    def shutdown(self):
        self._executor.shutdown(wait=False)

    def update(self):
        """Trigger a background refresh of the known source catalog."""
        if self._update_future is None or self._update_future.done():
            self._update_future = self._executor.submit(
                _load_known_sources, self.database_engine)

        if self._update_future is not None and self._update_future.done():
            try:
                self.ks_database = self._update_future.result()
            except Exception:
                import traceback; traceback.print_exc()
            self._update_future = None

    def _perform_action(self, event):
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
        if np.in1d(event.l1_events["beam"],
                   self.incoherent_beam_ids).all():
            ks_region, _ = nearby_known_sources_window(self.ks_database,
                event.ra, event.dm, self.sky_region,
                event.dm_error * self.dm_region)
        else:
            ks_region, _ = nearby_known_sources_circle(
                self.ks_database,
                event.ra,
                event.dec,
                event.dm,
                self.sky_region,
                event.dm_error * self.dm_region,
            )

        # only perform the comparison if there is something to compare with
        if ks_region.size > 0:
            probability = self.calculate_response(event, ks_region)

            probability_max = np.nanmax(probability)

            # does the most likely association meet the assoc. threshold?
            if probability_max > self.threshold:
                best_match = ks_region[np.argmax(probability)]

                # find the ID of the known source in the KS database
                source_name = best_match["source_name"]

                # remove the side-lobe copy identifier, if present
                if "_" in source_name:
                    source_name = source_name.split("_")[0]

                event['known_source_name'] = source_name

                event['known_source_rating'] = probability_max

                # i.e., do not override known source flag for RFI events
                if not event.is_rfi():
                    event['is_known_source'] = True

        return [event]

    def load_filters(self):
        """Initializes the filters defined in the configuration file.

        Function appends to `ks_filter_names` and `ks_filter_weights`.

        """
        # set sifter threshold
        self.threshold = float(self.threshold)

        # initialize filters
        for filt in self.filters:
            # check if this filter definition exists
            if hasattr(known_source_filters, filt[0]):
                self.ks_filter_names.append(filt[0])
                self.ks_filter_weights.append(float(filt[1]))
                print("Filter '{0}' loaded".format(filt[0]))
            else:
                print("Filter '{0}' is not defined in known_source_filters.py!".format(filt[0]))

        if not self.ks_filter_names:
            print("There are no filters defined! No known sources will be recognized!")

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
