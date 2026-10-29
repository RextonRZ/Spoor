from enum import StrEnum


class EvidenceLabel(StrEnum):
    """User-visible evidence category for every state and path (PRD §6.2, §18.1)."""

    OBSERVED = "observed"
    ESTIMATED = "estimated"
    HYPOTHESIZED = "hypothesized"
    UNKNOWN = "unknown"
    CONTRADICTED = "contradicted"


class SpatialMode(StrEnum):
    """How a position was obtained; every rendered marker carries one (PRD §13.5)."""

    MULTIVIEW_XYZ = "multiview_xyz"
    FLOOR_XY = "floor_xy"
    ANCHORED_HEIGHT = "anchored_height"
    ZONE_ONLY = "zone_only"
    IMAGE_ONLY = "image_only"
    UNKNOWN = "unknown"


class AssetKind(StrEnum):
    """Distinguished on every UI surface and export (PRD §7.3)."""

    ORIGINAL = "original"
    ANNOTATED_DERIVATIVE = "annotated_derivative"
    WORKING_DERIVATIVE = "working_derivative"  # transcode/proxy/keyframe: same content, different encoding
    ESTIMATED_GEOMETRY = "estimated_geometry"
    ILLUSTRATIVE = "illustrative"


class SourceType(StrEnum):
    VIDEO = "video"
    SENSOR_REAL = "sensor_real"
    SENSOR_SIMULATED = "sensor_simulated"  # must stay labelled simulated end to end (PRD §8.1)
    SCAN_REAL = "scan_real"  # barcode/RFID scan logs from a real WMS/sorter
    SCAN_SIMULATED = "scan_simulated"  # generated scan logs (e.g. from a Blender scenario); labelled end to end
    HUMAN_ANNOTATION = "human_annotation"


class RigState(StrEnum):
    """Calibration state; runtime tools check the state a method requires (PRD §13.4.2)."""

    UNCALIBRATED = "uncalibrated"
    CALIBRATING = "calibrating"
    VALIDATED_FLOOR_ONLY = "validated_floor_only"
    VALIDATED_MULTIVIEW_3D = "validated_multiview_3d"
    INVALIDATED = "invalidated"


class HypothesisStatus(StrEnum):
    PROPOSED = "proposed"
    EVALUATED = "evaluated"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


# proposed -> evaluated -> supported | contradicted | insufficient_evidence (PRD §11.3).
# A decided hypothesis may be re-opened to `evaluated` when new evidence arrives (PRD §5.2 step 7); history is kept.
HYPOTHESIS_TRANSITIONS: dict[HypothesisStatus, frozenset[HypothesisStatus]] = {
    HypothesisStatus.PROPOSED: frozenset({HypothesisStatus.EVALUATED}),
    HypothesisStatus.EVALUATED: frozenset(
        {HypothesisStatus.SUPPORTED, HypothesisStatus.CONTRADICTED, HypothesisStatus.INSUFFICIENT_EVIDENCE}
    ),
    HypothesisStatus.SUPPORTED: frozenset({HypothesisStatus.EVALUATED}),
    HypothesisStatus.CONTRADICTED: frozenset({HypothesisStatus.EVALUATED}),
    HypothesisStatus.INSUFFICIENT_EVIDENCE: frozenset({HypothesisStatus.EVALUATED}),
}

DECIDED_STATUSES = frozenset(
    {HypothesisStatus.SUPPORTED, HypothesisStatus.CONTRADICTED, HypothesisStatus.INSUFFICIENT_EVIDENCE}
)


class VerificationVerdict(StrEnum):
    """Verifier output (PRD §17.4). `unsupported` removes a claim from the factual summary."""

    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNSUPPORTED = "unsupported"


class FindingStatus(StrEnum):
    SUPPORTED_BY_VIDEO = "supported_by_video"
    SUPPORTED_BY_SENSOR = "supported_by_sensor"
    SUPPORTED_BY_VIDEO_AND_SENSOR = "supported_by_video_and_sensor"


class ActorKind(StrEnum):
    HUMAN = "human"
    AGENT = "agent"  # LLM-backed; may propose, never decide (PRD §11.3)
    VERIFIER_SERVICE = "verifier_service"  # deterministic verification engine (step 07)
    SYSTEM = "system"  # deterministic pipeline (ingest, perception, geometry)


class Role(StrEnum):
    SITE_ADMIN = "site_admin"
    INVESTIGATOR = "investigator"
    REVIEWER = "reviewer"


class AgentRole(StrEnum):
    LEAD = "lead"
    EVIDENCE = "evidence"
    HYPOTHESIS = "hypothesis"
    VERIFIER = "verifier"


class ObjectVisibility(StrEnum):
    """Object state machine; gaps never collapse into continuous motion (PRD §16.3)."""

    UNOBSERVED = "unobserved"
    VISIBLE = "visible"
    PARTIALLY_OCCLUDED = "partially_occluded"
    OUT_OF_VIEW = "out_of_view"
    VISIBLE_AGAIN = "visible_again"


class AssociationStatus(StrEnum):
    """Cross-track link status (PRD §14.3 step 8)."""

    VERIFIED_SAME_CAMERA = "verified_same_camera"
    # Exactly one track crossed the scan point's camera zone inside the scan's time window (identity from the scan)
    SCAN_BOUND = "scan_bound"
    CANDIDATE_CROSS_CAMERA = "candidate_cross_camera"
    HUMAN_CONFIRMED = "human_confirmed"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


class ZoneKind(StrEnum):
    SHELF = "shelf"
    DESK = "desk"
    DOOR = "door"
    HALLWAY = "hallway"
    WALKWAY = "walkway"
    OTHER = "other"


class SensorKind(StrEnum):
    DOOR_CONTACT = "door_contact"
    WEIGHT_DELTA_KG = "weight_delta_kg"
    RFID_TAG_SEEN = "rfid_tag_seen"
    MOTION_TRIGGER = "motion_trigger"
