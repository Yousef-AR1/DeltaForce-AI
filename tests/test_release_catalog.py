from config import BASE_DIR
from services.release_catalog_service import ReleaseCatalogService


def svc():
    return ReleaseCatalogService(BASE_DIR / "data" / "release_versions_catalog.json")


def test_mobile_release_query_is_direct():
    s = svc()
    assert s.can_handle("متى لعبة دلتا فورس توفرت لاجهزة موبايل؟")
    answer, _ = s.answer("متى لعبة دلتا فورس توفرت لاجهزة موبايل؟", "ar")
    assert "21 أبريل 2025" in answer
    assert "Android" in answer
    assert "iOS" in answer


def test_pc_release_has_both_milestones():
    answer, _ = svc().answer("متى نزلت Delta Force على PC؟", "ar")
    assert "5 ديسمبر 2024" in answer
    assert "21 أبريل 2025" in answer


def test_console_release():
    answer, _ = svc().answer("متى نزلت على PS5 وXbox؟", "ar")
    assert "19 أغسطس 2025" in answer
    assert "Xbox Series X|S" in answer


def test_versions_overview():
    answer, _ = svc().answer("شو النسخ الموجودة Garena والعالمية والصين؟", "ar")
    assert "Global" in answer
    assert "Garena" in answer
    assert "三角洲行动" in answer


def test_jordan_maps_to_garena_region():
    answer, _ = svc().answer("انا بالاردن وين انزل اللعبة واي نسخة؟", "ar")
    assert "Garena" in answer


def test_china_launch():
    answer, _ = svc().answer("متى نزلت نسخة الصين؟", "ar")
    assert "26 سبتمبر 2024" in answer
    assert "WeGame" in answer
