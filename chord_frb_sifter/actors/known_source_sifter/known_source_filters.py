"""This module defines the known source filters for the known source
sifter. An unused template function is defined below.

"""


import numpy as np
from chord_frb_sifter import config


def _tree_max_dm(itree):
    l1 = config.l1_config
    tree_dt = l1.dt_sample * l1.nds[itree] / l1.nups
    return ((l1.tree_size[itree] - 1) * tree_dt
            / (4.148806e3 * (1.0 / l1.freq_lo_MHz**2 - 1.0 / l1.freq_hi_MHz**2)))


def template(event, known_sources, weight, **kwargs):
    """An unused template known source filter.

    The `known_source_metrics` variable of `self` is updated by the
    function.

    Parameters
    ----------
    event : class
        Class should be ``L2Event``.

    known_sources : array_like
        A list of known sources.

    weight : float
        The relative weight for this filter.

    Returns
    -------
    response : array_like
        A list of floats, with the statistical response to all known
        sources.

    """

    print("Called template with arguments:")
    for key, value in list(kwargs.items()):
        print("{key} = {value}".format(key=key, value=value))

    assert isinstance(event, L2Event)

    # calculate the response
    response = np.empty(known_sources.size, dtype=np.float32)

    # add to the header dictionary 'known_source_metrics'
    # if the key already exists its values are updated
    if isinstance(event.get('known_source_metrics'), dict):
        event.known_source_metrics.update(
            {"template" + "_response": response, "template" + "_weight": weight}
        )
    else:
        event.known_source_metrics = {
            "template" + "_response": response,
            "template" + "_weight": weight,
        }

    return response


def compare_position(event, known_sources, weight, **kwargs):
    """Compare the sky position of `event` with the sky positions
    of the sources in `known_sources` using the Bayes factor.

    The function first calculates the angular sky separation between
    `event` and the sources in `known_sources`, and then computes the
    Bayes factor based on the likelihoods of the event being associated
    with a known source and being associated with a new random sky
    position. The response for each known source is stored in the
    `known_source_metrics` variable of `self`.

    Parameters
    ----------
    event : class
        Class should be ``L2Event``.

    known_sources : array_like
        A list of known sources.

    weight : float
        The relative weight for this filter compared to other filters.

    Returns
    -------
    response : float, array
        A list of floats, with the Bayes factor for all known sources in
        `known_sources`.

    Notes
    -----
    For a derivation of the Bayes factor for angular separation of two
    astronomical sources, see e.g. [1]_.

    References
    ----------
    .. [1] Budavari, T. & Szalay, A. S. 2008, ApJ, 679, 301-309

    """
    # default to 0, 1000, 2000 and 3000 if not specified
    incoherent_beam_ids = kwargs.get("incoherent_beam_ids", [0, 1000, 2000, 3000])

    if np.in1d(event.l1_events["beam"], incoherent_beam_ids).all():
        mu_min = 0
        mu_max = 360

        # add in declination-dependence of uncertainty
        correction_factor = np.cos(np.deg2rad(known_sources['pos_dec_deg']))
        # at NCP all 360 degrees in RA are constantly in the beam
        correction_factor[correction_factor > 180.] = 180.
        ra_uncertainty = event.ra_err / \
            correction_factor

        # calculate Bayes factor
        bayes_factor = gaussian_bayes(event.ra, ra_uncertainty,
                                      known_sources['pos_ra_deg'], mu_min,
                                      mu_max, wrap_around=True)
    else:
        # calculate angular separations
        angle, sep = angular_separation(
            event.ra,
            event.dec,
            known_sources["pos_ra_deg"],
            known_sources["pos_dec_deg"],
        )

        sigma_event = position_uncertainty(
            event.dec_err,
            event.ra_err,
            0.,
            angle,
        )

        # if the angle between source A and source B is x degrees,
        # the angle between source B and source A is (x + 180) % 360 degrees
        sigma_ks = position_uncertainty(0.1, 0.1, 0., (angle + 180) % 360)

        bayes_factor = position_bayes(sep, sigma_event, sigma_ks)

    # add to the header dictionary 'known_source_metrics'
    # if the key already exists its values are updated
    if isinstance(event.get('known_source_metrics'), dict):
        event.known_source_metrics.update({"position_weight": weight})
        for i, ks_name in enumerate(known_sources["source_name"]):
            event.known_source_metrics.update(
                {
                    "position_bayes_factor_{}".format(
                        ks_name
                    ): bayes_factor[i]
                }
            )
    else:
        event.known_source_metrics = {"position_weight": weight}
        for i, ks_name in enumerate(known_sources["source_name"]):
            event.known_source_metrics.update(
                {
                    "position_bayes_factor_{}".format(
                        ks_name
                    ): bayes_factor[i]
                }
            )

    return bayes_factor


def compare_dm(event, known_sources, weight, **kwargs):
    """Compare the dispersion measures (DMs) of `event` with the DMs
    of the sources in `known_sources` using the Bayes factor.

    The function first calculates the DM offsets between `event` and
    the sources in `known_sources`, and then computes the Bayes factor
    based on the likelihoods of the event being associated with a known
    source and being associated with a new random DM. The Bayes factor
    for each known source is stored in the `known_source_metrics`
    variable of `self`.

    Parameters
    ----------
    event : class
        Class should be ``L2Event``.
    known_sources : array_like
        A list of known sources.
    weight : float
        The relative weight for this filter compared to other filters.

    Returns
    -------
    bayes_factor : float, array
        A list of floats, with the Bayes factor for all known sources in
        `known_sources`.

    Notes
    -----
    For a derivation of the Bayes factor for a Gaussian variable without
    free parameters, see e.g. section 5.4 in [1]_.

    References
    ----------
    .. [1] Ivezic, Z., Connelly, A. J., VanderPlas, J. T. & Gray, A.
       2014, Statistics, Data Mining, and machine Learning in Astronomy,
       Princeton University Press, 2014

    """
    # calculate max DM for downsampling tree with best detection
    best = event.l1_events[event.l1_events["snr"].argmax()]
    mu_min = 0.0
    mu_max = _tree_max_dm(best["tree_index"])

    # calculate fine-grained DM step size from coarse-grained DM size
    # TODO import `dm_coarse_graining_factor` from bonsai config
    dm_coarse_graining_factor = 64  # / 8  # TODO only sampling 8 seems fine
    ddm_fine = 2 * event.dm_error / dm_coarse_graining_factor
    fine_grained_dms = np.arange(
        event.dm - event.dm_error + 0.5 * ddm_fine, event.dm + event.dm_error, ddm_fine
    )

    # calculate Bayes factor for all fine-grained steps and take the maximum
    bayes_factor = gaussian_bayes(
        fine_grained_dms, event.dm_error, known_sources["dm"], mu_min, mu_max
    )
    bayes_factor = bayes_factor.reshape(
        len(known_sources), dm_coarse_graining_factor
    ).max(axis=1)

    # add to the header dictionary 'known_source_metrics'
    # if the key already exists its values are updated
    if isinstance(event.get('known_source_metrics'), dict):
        event.known_source_metrics.update({"dm_weight": weight})
        for i, ks_name in enumerate(known_sources["source_name"]):
            event.known_source_metrics.update(
                {"dm_bayes_factor_{}".format(ks_name): bayes_factor[i]}
            )
    else:
        event.known_source_metrics = {"dm_weight": weight}
        for i, ks_name in enumerate(known_sources["source_name"]):
            event.known_source_metrics.update(
                {"dm_bayes_factor_{}".format(ks_name): bayes_factor[i]}
            )

    return bayes_factor


def angular_separation(ra1, dec1, ra2, dec2):
    """Calculates the angular separation between two celestial objects.

    Parameters
    ----------
    ra1 : float, array
        Right ascension of the first source in degrees.
    dec1 : float, array
        Declination of the first source in degrees.
    ra2 : float, array
        Right ascension of the second source in degrees.
    dec2 : float, array
        Declination of the second source in degrees.

    Returns
    -------
    angle : float, array
        Angle between the two sources in degrees, where 0 corresponds
        to the positive Dec axis.
    angular_separation : float, array
        Angular separation between the two sources in degrees.

    Notes
    -----
    The angle between sources is calculated with the Pythagorean theorem
    and is used later to calculate the uncertainty in the event position
    in the direction of the known source.

    Calculating the angular separation using spherical geometry gives
    poor accuracy for small (< 1 degree) separations, and using the
    Pythagorean theorem fails for large separations (> 1 degrees).
    Transforming the spherical geometry cosine formula into one that
    uses haversines gives the best results, see e.g. [1]_. This gives:

    .. math:: \mathrm{hav} d = \mathrm{hav} \Delta\delta +
              \cos\delta_1 \cos\delta_2 \mathrm{hav} \Delta\\alpha

    Where we use the identity
    :math:`\mathrm{hav} \\theta = \sin^2(\\theta/2)` in our
    calculations.

    The calculation might give inaccurate results for antipodal
    coordinates, but we do not expect such calculations here..

    The source angle (or bearing angle) :math:`\\theta` from a point
    A(ra1, dec1) to a point B(ra2, dec2), defined as the angle in
    clockwise direction from the positive declination axis can be
    calculated using:

    .. math:: \\tan(\\theta) = (\\alpha_2 - \\alpha_1) /
              (\delta_2 - \delta_1)

    In NumPy :math:`\\theta` can be calculated using the arctan2
    function. Note that for negative :math:`\\theta` a factor :math:`2\pi`
    needs to be added. See also the documentation for arctan2.

    References
    ----------
    .. [1] Sinnott, R. W. 1984, Sky and Telescope, 68, 158

    Examples
    --------
    >>> print(angular_separation(200.478971, 55.185900, 200.806433, 55.247994))
    (79.262937451490941, 0.19685681276638525)
    >>> print(angular_separation(0., 20., 180., 20.))
    (90.0, 140.0)

    """
    # convert decimal degrees to radians
    deg2rad = np.pi / 180
    ra1 = ra1 * deg2rad
    dec1 = dec1 * deg2rad
    ra2 = ra2 * deg2rad
    dec2 = dec2 * deg2rad

    # delta works
    dra = ra1 - ra2
    ddec = dec1 - dec2

    # haversine formula
    hav = np.sin(ddec / 2.0) ** 2 + np.cos(dec1) * np.cos(dec2) * np.sin(dra / 2.0) ** 2
    angular_separation = 2 * np.arcsin(np.sqrt(hav))

    # angle in the clockwise direction from the positive dec axis
    # note the minus signs in front of `dra` and `ddec`
    source_angle = np.arctan2(-dra, -ddec)
    source_angle[source_angle < 0] += 2 * np.pi

    # convert radians back to decimal degrees
    return source_angle / deg2rad, angular_separation / deg2rad


def position_uncertainty(semi_major, semi_minor, ellipse_angle, source_angle):
    """Calculate the uncertainty in position in the direction of a known
    source, given the positional uncertainty ellipse of a known source.

    Parameters
    ----------
    semi_major : float
        The ellipse's semi-major axis in degrees.
    semi_minor : float
        The ellipse's semi-minor axis in degrees.
    ellipse_angle : float
        The rotation angle of the ellipse in degrees (East of North).
    source_angle : float
        The angle towards the other sky location.

    Returns
    -------
    uncertainty : float
        The positional uncertainty in degrees in the direction of
        `source_angle`.

    Notes
    -----
    The parametric equation of an ellipse, with the semi-major axis
    pointing North for :math:`\\theta` is 0:

    .. math: x(t) = a \cos(t) \sin(\\theta) - b \sin(t) \cos(\\theta)
    .. math: y(t) = a \cos(t) \cos(\\theta) + b \sin(t) \sin(\\theta)

    Where, :math:`a` is the semi-major axis, :math:`b` is the semi-minor
    axis, :math:`t` is the clockwise angle around the ellipse for which
    x and y are calculated, and :math:`\\theta` is the rotation angle of
    the ellipse.

    The positional uncertainty is caculated using the Pythagorean theorem
    and :math:`x` and :math:`y`.

    """
    # convert decimal degrees to radians
    deg2rad = np.pi / 180
    semi_major = semi_major * deg2rad
    semi_minor = semi_minor * deg2rad
    ellipse_angle = ellipse_angle * deg2rad
    source_angle = source_angle * deg2rad

    # point on the error ellipse's side in the direction of a known source
    x = semi_major * np.cos(source_angle) * np.sin(ellipse_angle) - semi_minor * np.sin(
        source_angle
    ) * np.cos(ellipse_angle)
    y = semi_major * np.cos(source_angle) * np.cos(ellipse_angle) + semi_minor * np.sin(
        source_angle
    ) * np.sin(ellipse_angle)

    # Pythagoras
    position_uncertainty = np.sqrt(x ** 2 + y ** 2)

    # convert radians back to decimal degrees
    return position_uncertainty / deg2rad


def gaussian_bayes(x, sigma, mu, mu_min, mu_max, wrap_around=False):
    """Calculates the Bayes factor for a Gaussian variable.

    Parameters
    ----------
    x : float, array
        Observed value (e.g. DM of the event).
    sigma : float, array
        Uncertainty on the observed value (e.g. uncertainty on the DM
        of the event).
    mu : float, array
        Mean of Gaussian distribution to compare to (e.g. the DM of a
        known source).
    mu_min : float, array
        The lower limit on the variable being compared (e.g. range of
        DMs in CHIME/FRB, so 0 pc cm-3).
    mu_max : float, array
        The upper limit on the variable being compared (e.g. range of
        DMs in CHIME/FRB, so 13000 pc cm-3).
    wrap_around : bool
        Calculate the distance between the variable and the mean using
        modulo arithmetic if variable wraps around (as e.g. RA does).
        (Default: False)

    Returns
    -------
    bayes_factor : float, array
        Results of the comparisons.

    Notes
    -----
    For a derivation of the Bayes factor for a Gaussian variable without
    free parameters, see e.g. section 5.4 in [1]_.

    References
    ----------
    .. [1] Ivezic, Z., Connelly, A. J., VanderPlas, J. T. & Gray, A.
       2014, Statistics, Data Mining, and machine Learning in Astronomy,
       Princeton University Press, 2014

    """
    # match dimensions of `x` and `mu`
    mu = np.atleast_1d(mu)
    x = np.array([x] * len(mu)).T

    prefactor = 1.0 / (np.sqrt(2 * np.pi) * sigma) * (mu_max - mu_min)
    if wrap_around:
        # distance in modulo arithmetic
        d1 = (x - mu).T % mu_max
        d2 = (mu - x).T % mu_max
        distance = np.minimum(d1, d2)
    else:
        distance = np.abs(x - mu).T
    exponent = -1.0 / (2 * sigma ** 2) * distance ** 2
    bayes_factor = prefactor * np.exp(exponent)
    return bayes_factor


def position_bayes(angular_separation, sigma1, sigma2):
    """Calculates the Bayes factor for an angular separation.

    Parameters
    ----------
    angular_separation : float, array
        Angular separation between two sources in degrees.
    sigma1 : float, array
        Position uncertainty for the event in the direction
        of the known sources it is being compared with.
    sigma2 : float, array
        Position uncertainty for the known sources in the direction
        of the event.

    Returns
    -------
    bayes_factor : float, array
        Results of the comparisons.

    Notes
    -----
    See e.g. [1]_.

    References
    ----------
    .. [1] Budavari, T. & Szalay, A. S. 2008, ApJ, 679, 301-309

    """
    squared_sigma = sigma1 ** 2 + sigma2 ** 2
    prefactor = 2.0 / squared_sigma
    exponent = -1.0 * angular_separation ** 2 / (2 * squared_sigma)
    bayes_factor = prefactor * np.exp(exponent)
    return bayes_factor


if __name__ == "__main__":
    print(angular_separation(200.478971, 55.185900, 200.806433, 55.247994))
    print(angular_separation(0.0, 20.0, 180.0, 20.0))
    print(position_uncertainty(1.0, 2.0, 0.0, 0.0))
    print(position_uncertainty(1.0, 2.0, 0.0, 45.0))
    print(position_uncertainty(1.0, 2.0, 0.0, 90.0))
