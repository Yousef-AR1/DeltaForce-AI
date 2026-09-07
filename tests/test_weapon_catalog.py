from config import BASE_DIR
from services.weapon_catalog_service import WeaponCatalogService


def svc():
    return WeaponCatalogService(BASE_DIR / "data" / "weapons_catalog.json")


def test_total_is_66():
    assert svc().data["total_weapons"] == 66


def test_lmg_detection_arabic():
    assert svc().detect_category("اعطيني جميع اسامي اسلحه بفئه الرشاش الخفيف") == "lmg"


def test_lmg_complete():
    answer, _ = svc().category_answer("lmg", "ar")
    for name in ["M249", "PKM", "M250", "QJB201"]:
        assert name in answer


def test_shotguns_complete():
    answer, _ = svc().category_answer("shotgun", "ar")
    for name in ["S12K", "M1014", "M870", "725 Double-Barrel", "FS-12"]:
        assert name in answer


def test_followup():
    assert svc().is_followup("في اسلحه اخرى؟")
