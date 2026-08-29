import pytest
from pydantic import ValidationError

from threedog.style.profile import StyleProfile


def test_defaults():
    p = StyleProfile(name="s", structure="gtd")
    assert p.naming.convention == "zh"
    assert p.presentation.portal == "minimal"
    assert p.options.inbox is True


def test_domain_requires_domains():
    with pytest.raises(ValidationError):
        StyleProfile(name="s", structure="domain")


def test_full_profile():
    p = StyleProfile(name="工作台", structure="domain",
                     options={"domains": ["职业发展"], "inbox": False},
                     naming={"convention": "emoji",
                             "emoji_map": {"职业发展": "💼"}},
                     presentation={"portal": "dashboard"})
    assert p.naming.emoji_map["职业发展"] == "💼"
    assert p.options.inbox is False
