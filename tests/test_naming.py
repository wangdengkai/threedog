from threedog.style.naming import display_name, sanitize
from threedog.style.profile import NamingSpec


def test_sanitize():
    assert sanitize("a<b>:c") == "abc"
    assert sanitize("CON") == "_CON"
    assert sanitize("目录. ") == "目录"
    assert sanitize("///") == "_"


def test_conventions():
    assert display_name("职业发展", NamingSpec()) == "职业发展"
    emo = NamingSpec(convention="emoji", emoji_map={"职业发展": "💼"})
    assert display_name("职业发展", emo) == "💼职业发展"
    assert display_name("未知", emo) == "📁未知"
    num = NamingSpec(convention="numbered")
    assert display_name("生活", num, index=2) == "02-生活"
    bi = NamingSpec(convention="bilingual", en_map={"职业发展": "Career"})
    assert display_name("职业发展", bi) == "Career-职业发展"
    assert display_name("生活", bi) == "生活"  # 无映射时原样
