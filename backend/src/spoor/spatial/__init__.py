"""Site geometry, floor calibration and projection (PRD §13). Deterministic; no model calls."""

from .clock import (
    AnchorPair,
    ClockFit,
    ClockFitError,
    fit_clock,
    normalize,
    normalize_device_time,
    ordering_is_determined,
    sync_from_fit,
    sync_from_shared_event,
)
from .frames import renderer_to_site, site_to_renderer
from .homography import CalibrationError, ValidationThresholds, fit_floor_calibration, invalidate
from .projection import ProjectionInput, project_observation

__all__ = [
    "AnchorPair",
    "CalibrationError",
    "ClockFit",
    "ClockFitError",
    "ProjectionInput",
    "ValidationThresholds",
    "fit_clock",
    "fit_floor_calibration",
    "invalidate",
    "normalize",
    "normalize_device_time",
    "ordering_is_determined",
    "project_observation",
    "renderer_to_site",
    "site_to_renderer",
    "sync_from_fit",
    "sync_from_shared_event",
]
