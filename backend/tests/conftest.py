from datetime import UTC, datetime

import pytest

from spoor.config import Settings
from spoor.contracts import Floor, Site, Zone, ZoneKind

# Tests are hermetic: they never read a developer's backend/.env (real API keys, local paths). Without this a key
# placed there for the real app would reach the tests and could trigger paid model calls.
Settings.model_config["env_file"] = None

NOW = datetime(2026, 10, 27, 14, 0, tzinfo=UTC)


@pytest.fixture
def now() -> datetime:
    return NOW


@pytest.fixture
def room() -> Site:
    """A 6 m x 4 m storeroom with a shelf, a desk and a door (test fixture, not demo data)."""
    return Site(
        site_id="site_test",
        name="Test storeroom",
        measurement_method="synthetic test fixture",
        floors=[Floor(floor_id="floor_g", name="Ground", outline_m=[(0, 0), (6, 0), (6, 4), (0, 4)])],
        zones=[
            Zone(zone_id="zone_shelf_a", floor_id="floor_g", name="Shelf A", kind=ZoneKind.SHELF,
                 polygon_m=[(0, 3.4), (2, 3.4), (2, 4), (0, 4)], surface_height_m=1.2, measured=True),
            Zone(zone_id="zone_desk", floor_id="floor_g", name="Desk", kind=ZoneKind.DESK,
                 polygon_m=[(3, 1), (4.5, 1), (4.5, 1.8), (3, 1.8)], surface_height_m=0.75, measured=True),
            Zone(zone_id="zone_door_b", floor_id="floor_g", name="Door B", kind=ZoneKind.DOOR,
                 polygon_m=[(5.2, 0), (6, 0), (6, 0.4), (5.2, 0.4)], measured=True),
        ],
    )  # fmt: skip


@pytest.fixture
def site(room):
    """The test room plus a hallway beyond Door B (floor extends south of y=0)."""
    floor = Floor(floor_id="floor_g", name="Ground", outline_m=[(0, -2), (6, -2), (6, 4), (0, 4)])
    hall = Zone(zone_id="zone_hall", floor_id="floor_g", name="Hallway", kind=ZoneKind.HALLWAY,
                polygon_m=[(4, -2), (6, -2), (6, -0.01), (4, -0.01)], measured=True)  # fmt: skip
    return room.model_copy(update={"floors": [floor], "zones": [*room.zones, hall]})
