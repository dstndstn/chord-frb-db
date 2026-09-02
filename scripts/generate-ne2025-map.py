#!/usr/bin/env python3
"""
Generate NE2025_map.npy for use in chord-frb-sifter's DMChecker.

Computes the maximum Galactic DM (integrated to 50 kpc) at each sky point
using mwprop NE2025, on the same RA/Dec grid as the existing NE2001_map.npy.

Output format: (N, 3) float64 array, columns = [RA_deg, Dec_deg, DM_max_pc_cm3]

Example usage:
    python generate-ne2025-map.py
    python generate-ne2025-map.py --nproc 8 --ds-fine 0.025 --out /path/to/NE2025_map.npy
"""

import argparse
import contextlib
import io
import multiprocessing as mp
import os
import time

import numpy as np

_DEFAULT_DATA_DIR = os.path.join(
    os.path.dirname(__file__), '..', 'chord_frb_sifter', 'data', 'dm_checker'
)


# ─── worker ──────────────────────────────────────────────────────────────────

def _init_worker(ds_fine):
    """Run once per worker process: import mwprop and cache module-level state."""
    import warnings
    warnings.filterwarnings('ignore')

    # importing dmdsm triggers config_nemod which sets up the model (slow, ~1s)
    from mwprop.nemod.dmdsm import dmdsm_d2dm, dmax_ne2001p_integrate
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    global _dmdsm_d2dm, _dmax, _ds_fine, _SkyCoord, _u
    _dmdsm_d2dm = dmdsm_d2dm
    _dmax = dmax_ne2001p_integrate
    _ds_fine = ds_fine
    _SkyCoord = SkyCoord
    _u = u


def _compute_one(args):
    """Compute DM_max for a single (RA, Dec) point. Returns (index, dm)."""
    idx, ra_deg, dec_deg = args

    sc = _SkyCoord(ra=ra_deg * _u.deg, dec=dec_deg * _u.deg, frame='icrs')
    l = sc.galactic.l.rad
    b = sc.galactic.b.rad

    # suppress the verbose print output from dmdsm_d2dm
    with contextlib.redirect_stdout(io.StringIO()):
        result = _dmdsm_d2dm(
            l, b, _dmax,
            ds_coarse=0.5, ds_fine=_ds_fine, Nsmin=5,
            d2dm_only=True, do_analysis=False, plotting=False, verbose=False,
        )

    return idx, float(result[2])


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--out', default=os.path.join(_DEFAULT_DATA_DIR, 'NE2025_map.npy'),
        help='Output .npy path (default: chord_frb_sifter/data/dm_checker/NE2025_map.npy)',
    )
    parser.add_argument(
        '--grid', default=None,
        help='Path to existing map whose RA/Dec grid to reuse (default: NE2001_map.npy next to --out)',
    )
    parser.add_argument(
        '--nproc', type=int, default=mp.cpu_count(),
        help=f'Worker processes (default: {mp.cpu_count()}, all CPUs)',
    )
    parser.add_argument(
        '--ds-fine', type=float, default=0.025,
        help='Fine integration step size in kpc (default: 0.025; smaller = more accurate but slower)',
    )
    args = parser.parse_args()

    if args.grid is None:
        args.grid = os.path.join(os.path.dirname(args.out), 'NE2001_map.npy')

    # load grid
    existing = np.load(args.grid)
    ra_arr  = existing[:, 0]
    dec_arr = existing[:, 1]
    N = len(ra_arr)

    print(f'Grid:    {N} points from {args.grid}')
    print(f'Workers: {args.nproc}')
    print(f'ds_fine: {args.ds_fine} kpc  (accuracy ~0.1 pc/cm³ vs default 0.01 kpc)')
    print(f'Output:  {args.out}')
    est_s = N * 0.20 / args.nproc
    print(f'Estimated time: {est_s/60:.0f} min')
    print()

    tasks = [(i, ra_arr[i], dec_arr[i]) for i in range(N)]
    dm_out = np.empty(N, dtype=np.float64)

    t0 = time.perf_counter()
    with mp.Pool(
        processes=args.nproc,
        initializer=_init_worker,
        initargs=(args.ds_fine,),
    ) as pool:
        for done, (idx, dm) in enumerate(
            pool.imap_unordered(_compute_one, tasks, chunksize=20), 1
        ):
            dm_out[idx] = dm
            if done % 200 == 0 or done == N:
                elapsed = time.perf_counter() - t0
                rate = done / elapsed
                eta = (N - done) / rate
                print(
                    f'  {done}/{N} ({100*done/N:.1f}%)  '
                    f'elapsed {elapsed/60:.1f} min  '
                    f'ETA {eta/60:.1f} min    ',
                    end='\r', flush=True,
                )

    elapsed = time.perf_counter() - t0
    print(f'\nCompleted {N} points in {elapsed/60:.1f} min')

    out_arr = np.column_stack([ra_arr, dec_arr, dm_out])
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    np.save(args.out, out_arr)
    print(f'Saved {out_arr.shape} array to {args.out}')
    print(f'DM range: {dm_out.min():.1f} – {dm_out.max():.1f} pc/cm³')


if __name__ == '__main__':
    main()
