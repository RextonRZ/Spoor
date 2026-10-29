"""Coordinate-frame conversions (PRD §13.5).

Site frame: X right/east, Y forward/north, Z up, metres (right-handed).
glTF / Three.js renderer frame: Y up, right-handed, +Z toward the default viewer.
site (x, y, z) -> renderer (x, z, -y): a -90° rotation about X, so handedness is preserved.
"""

import numpy as np

SITE_TO_RENDERER = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]])
RENDERER_TO_SITE = SITE_TO_RENDERER.T


def site_to_renderer(xyz: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = SITE_TO_RENDERER @ np.asarray(xyz, dtype=np.float64)
    return float(x), float(y), float(z)


def renderer_to_site(xyz: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = RENDERER_TO_SITE @ np.asarray(xyz, dtype=np.float64)
    return float(x), float(y), float(z)
