from config import BASE_DIR
from services.game_catalog_service import GameCatalogService


def svc():
    return GameCatalogService(BASE_DIR / "data")


def test_current_operator_count():
    assert svc().operators["current_count"] == 17


def test_rover_is_upcoming_not_current():
    rover = svc().operators["upcoming_operators"][0]
    assert rover["codename"] == "Rover"
    assert rover["status"] == "upcoming"
    assert rover["release_date"] == "2026-09-08"


def test_operations_maps_complete():
    names = [x["name"] for x in svc().maps["operations"]["maps"]]
    assert names == ["Zero Dam", "Layali Grove", "Space City", "Brakkesh", "Tide Prison", "AZ3"]


def test_warfare_hq_map_count():
    assert len(svc().maps["warfare"]["official_hq_visible_maps"]) == 14
    assert svc().maps["warfare"]["verified_current_or_referenced_count"] == 15


def test_operator_list_query_is_direct():
    s = svc()
    assert s.can_handle("اعطيني جميع الشخصيات الحالية")
    answer, _ = s.answer("اعطيني جميع الشخصيات الحالية", "ar")
    assert "17" in answer
    assert "N-Two" in answer
    assert "Rover" in answer


def test_latest_query_separates_reorientation():
    answer, _ = svc().answer("شو الموسم الحالي وآخر تحديث؟", "ar")
    assert "Meltdown" in answer
    assert "Reorientation" in answer
    assert "2026-09-08" in answer


def test_master_query():
    answer, _ = svc().answer("شو عندك كلشي عن اللعبة؟", "ar")
    assert "66" in answer
    assert "17" in answer
