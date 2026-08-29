import pytest

from threedog.actions.strategies import LinkStrategy, get_strategy, symlink_ok


@pytest.mark.parametrize("name", ["copy", "move", "link"])
def test_execute_and_rollback(name, tmp_path):
    # 说明：原 brief 中 `pytest.mark.skipif(...)()` 在函数体内运行时是 no-op，
    # 无软链权限时无法跳过；改用与 brief 第二个测试一致的运行时跳过方式，
    # 跳过条件与原因字符串保持 verbatim。
    if name == "link" and not symlink_ok():
        pytest.skip("无软链权限")
    src = tmp_path / "s.txt"
    src.write_text("data")
    dst = tmp_path / "out" / "d.txt"
    strat = get_strategy(name)
    info = strat.execute(src, dst)
    assert dst.exists() and dst.read_text() == "data"
    if name == "move":
        assert not src.exists()
    strat.rollback(dst, info)
    assert not dst.exists()
    if name == "move":
        assert src.exists() and src.read_text() == "data"
    if name == "link":
        assert src.exists()


def test_link_strategy_is_symlink(tmp_path):
    if not symlink_ok():
        pytest.skip("无软链权限")
    src = tmp_path / "s.txt"
    src.write_text("x")
    dst = tmp_path / "d.txt"
    LinkStrategy().execute(src, dst)
    assert dst.is_symlink()
