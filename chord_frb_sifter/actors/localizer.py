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

<<<<<<< HEAD
        if len(snrs) == 1:
            x_out, y_out = x[0], y[0]
            x_err, y_err = sigma_x, sigma_y
        else:
            x_out, y_out, x_err, y_err = fit_2dgauss_analytical_jac(
                x, y, snrs, sigma_x, sigma_y
            )
            # Rank-deficient Jacobian (one-sided cluster at FOV edge): fall
            # back to the peak-SNR beam centre with beam sigma rather than
            # propagating NaN error bars downstream.
            if np.isnan(x_err) or np.isnan(y_err):
                peak_i = np.argmax(snrs)
                x_out, y_out = x[peak_i], y[peak_i]
                x_err, y_err = sigma_x, sigma_y
=======
        # fix this after making L1Events recarray?
        beams = []
        snrs = []
        for e in event["l1_events"]:
            beams.append(e["beam_id"])
            snrs.append(e["snr"])
        beams = np.array(beams)
        snrs = np.array(snrs)
>>>>>>> main

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


def jacobian_gauss2d_analytical_width(p0, xy, sigma_x, sigma_y, snr):
    """Analytic Jacobian of residuals_gauss2d_analytical_width w.r.t. (x0, y0).

    Differentiates through the analytically-solved amplitude A = dot(g,snr)/dot(g,g).
    Returns (n_beams, 2) array.
    """
    x0, y0 = p0
    x, y = xy[0], xy[1]
    g = gauss2d(xy, 1.0, x0, y0, sigma_x, sigma_y)
    G = np.dot(g, g)
    if G == 0:
        return np.zeros((len(snr), 2))
    A = np.dot(g, snr) / G

    dg_dx0 = g * (x - x0) / sigma_x**2
    dg_dy0 = g * (y - y0) / sigma_y**2

    dA_dx0 = (np.dot(dg_dx0, snr) - 2.0 * A * np.dot(g, dg_dx0)) / G
    dA_dy0 = (np.dot(dg_dy0, snr) - 2.0 * A * np.dot(g, dg_dy0)) / G

    J = np.empty((len(snr), 2))
    J[:, 0] = -dA_dx0 * g - A * dg_dx0
    J[:, 1] = -dA_dy0 * g - A * dg_dy0
    return J


def _covariance_from_jac(jac, residuals):
    """Compute position covariance from least-squares Jacobian and residuals.

    pcov = sigma² · (J^T J)⁺  where sigma² = ||r||² / (n − 2) and (J^T J)⁺
    is the Moore-Penrose pseudo-inverse via SVD. Using the pseudo-inverse
    handles rank-deficient cases (e.g. beams only on one side of the source at
    the FOV edge) without exceptions or spurious negative covariances:
    near-zero singular values map to np.nan in that direction only.

    Returns (x_err, y_err). Either may be np.nan if that direction is
    unconstrained; (nan, nan) if J is identically zero.
    """
    n = len(residuals)
    if n <= 2:
        return np.nan, np.nan
    sigma_sq = np.dot(residuals, residuals) / (n - 2)

    _, s, Vt = np.linalg.svd(jac, full_matrices=False)
    if s[0] == 0:
        return np.nan, np.nan

    thresh = np.finfo(float).eps * max(jac.shape) * s[0]
    # For each singular value: finite 1/s² if constrained, inf if not.
    s_inv_sq = np.where(s > thresh, 1.0 / s**2, np.inf)
    # diag[(J^T J)^+]_i = sum_j Vt[j,i]^2 / s[j]^2
    pcov_diag = sigma_sq * np.sum(Vt**2 * s_inv_sq[:, np.newaxis], axis=0)

    x_err = float(np.sqrt(pcov_diag[0])) if np.isfinite(pcov_diag[0]) else np.nan
    y_err = float(np.sqrt(pcov_diag[1])) if np.isfinite(pcov_diag[1]) else np.nan
    return x_err, y_err


def fit_2dgauss_analytical_jac(x, y, snr, sigma_x, sigma_y):
    """Fit a 2D Gaussian to beam S/Ns using the analytic Jacobian.

    Drop-in replacement for fit_2dgauss_simplified. Same residual function,
    same covariance estimate, but supplies the analytic Jacobian so least_squares
    avoids finite-difference steps — faster and more robust near the boundary.
    """
    max_i = np.argmax(snr)
    p0 = [x[max_i], y[max_i]]

    result = least_squares(
        residuals_gauss2d_analytical_width,
        p0,
        jac=jacobian_gauss2d_analytical_width,
        args=([x, y], sigma_x, sigma_y, snr),
        bounds=([-1.0, -1.0], [1.0, 1.0]),
    )

    x_out, y_out = result.x
    x_err, y_err = _covariance_from_jac(result.jac, result.fun)
    return x_out, y_out, x_err, y_err


def fit_2dgauss_simplified(x, y, snr, sigma_x, sigma_y):
    """Fit a 2D Gaussian to beam S/Ns using finite-difference Jacobian.

    Kept for A/B comparison with fit_2dgauss_analytical_jac. Prefer
    fit_2dgauss_analytical_jac in production — it is faster and avoids FD
    perturbation steps near the parameter bounds.
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
    x_err, y_err = _covariance_from_jac(result.jac, result.fun)
    return x_out, y_out, x_err, y_err
