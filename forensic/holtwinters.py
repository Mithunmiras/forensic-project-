"""Holt-Winters exponential smoothing in numpy: additive damped trend + additive seasonality.

Smoothing parameters are chosen by grid search on the one-step-ahead squared error; every
grid point is filtered at once as a numpy vector, so a fit over ~270 days takes milliseconds.
Kept dependency-free so the API fits in a serverless function bundle.
"""
from __future__ import annotations

import itertools

import numpy as np

ALPHAS = (0.05, 0.1, 0.2, 0.3, 0.5)
BETAS = (0.01, 0.05, 0.1)
GAMMAS = (0.05, 0.1, 0.2, 0.3)
PHIS = (0.8, 0.9, 0.98)


def forecast(y, horizon: int, season: int = 7) -> np.ndarray:
    y = np.asarray(y, dtype=float)
    if len(y) < 2 * season:
        return np.full(horizon, y.mean() if len(y) else 0.0)
    grid = np.array(list(itertools.product(ALPHAS, BETAS, GAMMAS, PHIS)))
    alpha, beta, gamma, phi = grid.T
    k = len(grid)

    level = np.full(k, y[:season].mean())
    trend = np.full(k, (y[season:2 * season].mean() - y[:season].mean()) / season)
    seas = np.tile(y[:season] - y[:season].mean(), (k, 1))
    sse = np.zeros(k)
    for t, obs in enumerate(y):
        s = seas[:, t % season]
        sse += (obs - (level + phi * trend + s)) ** 2
        new_level = alpha * (obs - s) + (1 - alpha) * (level + phi * trend)
        trend = beta * (new_level - level) + (1 - beta) * phi * trend
        seas[:, t % season] = gamma * (obs - new_level) + (1 - gamma) * s
        level = new_level

    b = int(np.argmin(sse))
    steps = np.arange(1, horizon + 1)
    damped = np.cumsum(phi[b] ** steps)
    idx = (len(y) + steps - 1) % season
    return level[b] + damped * trend[b] + seas[b, idx]
