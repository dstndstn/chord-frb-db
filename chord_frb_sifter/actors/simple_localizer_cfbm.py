"""
SimpleLocalizerCFBM: SNR-weighted centroid localizer using the CHIME beam model.

Replaces the Gaussian-fit Localizer for cases where only a few beams are available.
Sets event.ra, event.dec, event.ra_err, event.dec_err.
"""

import numpy as np
from datetime import datetime

import cfbm

from chord_frb_sifter.actors import Actor

# Single-beam position uncertainty: CHIME beam half-width at ~600 MHz.
# FWHM ~ 0.5 deg -> sigma ~ FWHM / 2.35
_SINGLE_BEAM_SIGMA_DEG = 0.5 / 2.35


class SimpleLocalizerCFBM(Actor):
    """
    Localizes an event by computing the SNR-weighted mean beam position
    using the CHIME/CHORD beam model (cfbm), without fitting a 2D Gaussian.

    Works for single-beam events (returns beam centre + beam-size uncertainty)
    and multi-beam events (returns weighted centroid + positional spread).
    """

    def __init__(self, **kwargs):
        self.bm = cfbm.current_model_class()

    def _perform_action(self, event):
        l1_events = event['l1_events']
        beams = np.array([e['beam_id'] for e in l1_events])
        snrs  = np.array([e['snr']  for e in l1_events], dtype=float)

        # Shape: (N_beams, 1, 2) -> take first (only) freq -> (N_beams, 2)
        beam_poses = self.bm.get_beam_positions(beams, freqs=self.bm.clamp_freq)

        weighted_mean_pos = np.average(
            beam_poses[:, 0],
            weights=snrs,
            axis=0,
        )

        x, y = self.bm.get_cartesian_from_position(weighted_mean_pos[0], weighted_mean_pos[1])
        pos = self.bm.get_position_from_cartesian(x, y)
        t = datetime.utcfromtimestamp(event['timestamp_utc'] / 1e6)
        ra, dec = self.bm.get_equatorial_from_position(pos[0], pos[1], t)

        event['ra']  = ra
        event['dec'] = dec

        if len(beams) == 1:
            event['ra_err']  = _SINGLE_BEAM_SIGMA_DEG
            event['dec_err'] = _SINGLE_BEAM_SIGMA_DEG
        else:
            # Weighted std of beam positions in position space, converted to degrees.
            # Position coords are in sin(angle) ~ radians for small offsets.
            variance = np.average(
                (beam_poses[:, 0] - weighted_mean_pos) ** 2,
                weights=snrs,
                axis=0,
            )
            std_deg = np.rad2deg(np.sqrt(variance))
            event['ra_err']  = max(float(std_deg[0]), _SINGLE_BEAM_SIGMA_DEG)
            event['dec_err'] = max(float(std_deg[1]), _SINGLE_BEAM_SIGMA_DEG)

        return [event]
