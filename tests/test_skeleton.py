from threedog.style.profile import StyleProfile
from threedog.style.skeleton import CategoryNode, build_skeleton, flatten


def test_gtd_with_inbox():
    p = StyleProfile(name="s", structure="gtd")
    names = [n.name_raw for n in build_skeleton(p)]
    assert names == ["待整理", "收件箱", "下一步", "资料", "归档"]


def test_domain_without_inbox():
    p = StyleProfile(name="s", structure="domain",
                     options={"domains": ["职业发展", "生活"], "inbox": False})
    assert [n.name_raw for n in build_skeleton(p)] == ["职业发展", "生活"]


def test_project():
    p = StyleProfile(name="s", structure="project",
                     options={"projects": ["装修", "跳槽"], "inbox": False})
    assert [n.name_raw for n in build_skeleton(p)] == ["装修", "跳槽"]


def test_time_month():
    p = StyleProfile(name="s", structure="time", options={"inbox": False})
    (node,) = build_skeleton(p)
    assert node.name_raw.count("-") == 1  # 2026-08 形态


def test_flatten():
    root = CategoryNode("A", [CategoryNode("B", [CategoryNode("C")])])
    assert flatten([root]) == ["A", "A/B", "A/B/C"]
