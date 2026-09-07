from config import BASE_DIR
from services.semantic_intent_router import SemanticIntentRouter


def router():
    return SemanticIntentRouter(BASE_DIR / "data" / "intent_router_examples.json")


def assert_intent(text, expected):
    result = router().route(text)
    assert result is not None, text
    assert result.intent == expected, (text, result)


def test_current_season_jordanian():
    assert_intent("اي سيزن اللعبه الان؟", "current_season")


def test_current_season_levantine():
    assert_intent("شو السيزن هسا؟", "current_season")


def test_current_season_gulf():
    assert_intent("وش السيزن الحين؟", "current_season")


def test_current_season_egyptian():
    assert_intent("احنا في سيزون كام دلوقتي؟", "current_season")


def test_current_season_iraqi():
    assert_intent("شنو السيزن هسه؟", "current_season")


def test_current_season_maghrebi():
    assert_intent("فاش موسم حنا دابا؟", "current_season")


def test_current_season_english_colloquial():
    assert_intent("what season are we on rn?", "current_season")


def test_mobile_release_dialect():
    assert_intent("امتى نزلت اللعبه ع الجوال؟", "mobile_release")


def test_console_release_dialect():
    assert_intent("متى طلعت ع البلايستيشن والاكس بوكس؟", "console_release")


def test_all_operators_dialect():
    assert_intent("مين كل الشخصيات الموجودة هسا؟", "all_operators")


def test_all_modes_dialect():
    assert_intent("شو كل المودات باللعبة؟", "all_modes")


def test_lmg_dialect():
    assert_intent("هات كل الرشاشات الخفيفة", "all_lmg")
