"""
This a CHORD/FRB prototype for the localizer.

It determines the best-fit sky position of the event based on the S/N per beam.
"""

import numpy as np
from scipy.optimize import least_squares
from astropy.time import Time

from chord_frb_sifter.actors import Actor
from chord_frb_sifter.chord_telescope import ChordTelescope
from chord_frb_sifter import config

# CHORD beam FWHM at 900 MHz reference frequency, in unit-sphere (grid) coordinates.
# Scales as 1/freq for a diffraction-limited aperture: FWHM(f) = FWHM_900 * (900/f).
# TODO: derive from array layout instead of hardcoding. Requires dish_grid_size_x and
# dish_grid_size_y (number of dishes per axis) in the telescope config — these exist in
# kotekan's CHORDTelescope config schema but are not yet in our Python config/YAML.
# Formula: FWHM = λ / ((N-1) * dish_separation_m), where λ = c / f.
_FWHM_X_900 = 0.0046  # EW (radians)
_FWHM_Y_900 = 0.0068  # NS (radians)
_FREQ_REF_MHZ = 900.0


def beam_sigmas(central_freq_mhz):
    """Return (sigma_x, sigma_y) in grid coordinates for the given central frequency."""
    scale = _FREQ_REF_MHZ / central_freq_mhz
    return _FWHM_X_900 * scale / 2.355, _FWHM_Y_900 * scale / 2.355


class Localizer(Actor):
    """
    Determines the best-fit sky position of an astrophysical event
    based on the signal-to-noise ratio (S/N) measured in multiple telescope beams.

    Fits a 2D Gaussian function to the detected S/Ns with only the position in
    unit-sphere (grid) coordinates as free parameters. It then converts to equatorial
    coordinates (RA, Dec) using ChordTelescope.

    For single-beam events the fit is skipped; the beam centre is used as the
    position and the beam sigma is used as the positional uncertainty.

    Parameters
    ----------
    central_freq_mhz : float
        Central frequency of the subband in MHz. Used to compute beam width.
        Will be superseded by a per-event field once that is available in L1 data.
    """

    def __init__(self, central_freq_mhz=900.0, **kwargs):
        super().__init__(**kwargs)
        self.tele = ChordTelescope(config.chord_config.telescope)
        self.central_freq_mhz = central_freq_mhz

    def _perform_action(self, event):
        l1 = event["l1_events"]
        x    = l1["beam_grid_x"].astype(float)
        y    = l1["beam_grid_y"].astype(float)
        snrs = l1["snr"].astype(float)

        # TODO: read central_freq_mhz per-event from l1 once the field exists
        sigma_x, sigma_y = beam_sigmas(self.central_freq_mhz)

        if len(snrs) == 1:
            x_out, y_out = x[0], y[0]
            x_err, y_err = sigma_x, sigma_y
        else:
            x_out, y_out, x_err, y_err = fit_2dgauss_simplified(
                x, y, snrs, sigma_x, sigma_y
            )

        # Unit-sphere grid coords -> topocentric -> ITRS -> (RA, Dec)
        z_out = np.sqrt(max(0.0, 1.0 - x_out**2 - y_out**2))
        topo  = self.tele.grid_to_topocentric(x_out, y_out, z=z_out)
        itrs  = self.tele.topocentric_to_itrs(topo)
        t     = Time(event["timestamp_utc"] / 1e6, format="unix", scale="utc")
        ra, dec = self.tele.itrs_to_radec(itrs, t)

        event["ra"]      = ra
        event["dec"]     = dec
        # Small-angle approximation: grid errors (radians) -> sky errors (degrees)
        event["ra_err"]  = np.rad2deg(x_err)
        event["dec_err"] = np.rad2deg(y_err)

        return [event]


def gauss2d(xy, A, x0, y0, sigma_x, sigma_y):
    return A * np.exp(-(
        ((xy[0] - x0)**2) / (2 * sigma_x**2) +
        ((xy[1] - y0)**2) / (2 * sigma_y**2)
    ))


def residuals_gauss2d_analytical_width(p0, xy, sigma_x, sigma_y, snr):
    x0, y0 = p0
    gauss_xy = gauss2d(xy, 1.0, x0, y0, sigma_x, sigma_y)
    A = np.dot(gauss_xy, snr) / np.dot(gauss_xy, gauss_xy)
    return snr - A * gauss_xy


def fit_2dgauss_simplified(x, y, snr, sigma_x, sigma_y):
    """
    Fit a 2D Gaussian to beam S/Ns in unit-sphere grid coordinates.

    Amplitude is solved analytically at each trial position; only (x0, y0)
    are free parameters. Beam widths are passed in and should be computed
    from the subband central frequency via beam_sigmas().
    """
    max_i = np.argmax(snr)
    p0 = [x[max_i], y[max_i]]

    result = least_squares(
        residuals_gauss2d_analytical_width,
        p0,
        args=([x, y], sigma_x, sigma_y, snr),
        bounds=([-1.0, -1.0], [1.0, 1.0]),
    )

    x_out, y_out = result.x

    try:
        pcov = np.linalg.inv(result.jac.T @ result.jac)
        x_err, y_err = np.sqrt(np.diag(pcov))
    except np.linalg.LinAlgError:
        x_err, y_err = np.nan, np.nan

    return x_out, y_out, x_err, y_err
