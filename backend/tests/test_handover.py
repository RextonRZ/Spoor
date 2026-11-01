"""Carrier check by place and time (forensics/handover.py): no identity, only where things were at the same moments."""

import numpy as np

from spoor.forensics.handover import FloorPath, carrier_fit, heading

T = np.arange(0, 4000, 100.0)  # 4 s at 10 fps


def path(tid, xy, t=T, spread=0.0):
    return FloorPath(tid, "cam", np.asarray(t, float), np.asarray(xy, float), np.full(len(t), spread))


CARTON = path("carton", [(20 - 0.0013 * t, 31.0) for t in T], spread=0.5)  # walking west at 1.3 m/s


def test_person_at_the_carton_is_the_likely_carrier():
    f = carrier_fit(CARTON, path("a", [(20 - 0.0013 * t + 0.4, 31.2) for t in T]))
    assert f.verdict == "likely carrier" and f.shared_s >= 3.5


def test_far_person_is_ruled_out_with_a_reason():
    f = carrier_fit(CARTON, path("b", [(34.0, 30.0 + 0.001 * t) for t in T]))
    assert f.verdict == "not the carrier" and "m from the carton" in f.reason and "north" in f.reason


def test_person_gone_before_the_carton_appears():
    f = carrier_fit(CARTON, path("c", [(33.0, 35.0)] * 10, t=np.arange(-5000, -4000, 100.0)))
    assert f.verdict == "not the carrier" and "before the carton appeared" in f.reason


def test_brief_contact_is_not_enough():
    f = carrier_fit(CARTON, path("d", [(20 - 0.0013 * t, 31.0) for t in T[:10]], t=T[:10]))
    assert f.verdict == "not the carrier" and "only" in f.reason


def test_heading_words():
    assert heading(path("e", [(0, 0), (0, 5)], t=[0, 1])) == "north"
    assert heading(path("f", [(0, 0), (0.2, 0.1)], t=[0, 1])) == "standing still"
