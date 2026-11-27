"""site/tutorials/<name>.html are up to date with their folder of examples/tutorials/, and
examples/tutorials/page.py writes those pages alone: the packs' tutorials have their page in the studio."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("tutorial_page", ROOT / "examples" / "tutorials" / "page.py")
page = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(page)


def test_pages_are_up_to_date():
    pages = page.pages()
    assert page.page_of(page.HERE / "lunar_ground") in pages
    for path, text in pages.items():
        assert path.read_text(encoding="utf-8") == text, f"run `python3 examples/tutorials/page.py` ({path.name})"


def test_pages_are_those_site_tutorials_has():
    assert all(path.exists() for path in page.pages())


def test_a_tutorial_named_is_written_alone():
    assert list(page.pages(["toon_lights"])) == [page.SITE / "toon-lights.html"]
    with pytest.raises(SystemExit, match="no tutorial nowhere"):
        page.pages(["nowhere"])
