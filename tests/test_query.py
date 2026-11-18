import pytest

pytestmark = pytest.mark.modules("db")


def test_search_treats_wildcards_as_text():
    from sqlalchemy import column

    from app.modules.db.query import contains

    condition = contains(column("name"), "50%_off\\")
    assert condition.right.value == "%50\\%\\_off\\\\%"


def test_filter_values_and_sort_order():
    from sqlalchemy import column

    from app.modules.db.query import listed, ordered, sort_options

    assert listed("a,,b,x", ("a", "b")) == ["a", "b"]
    assert listed(None) == []
    assert sort_options(["name"]).__args__ == ("name", "-name")
    assert "DESC NULLS LAST" in str(ordered({"name": column("name")}, "-name"))
