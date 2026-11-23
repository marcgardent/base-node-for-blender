"""site/state-of-the-art-autumn-2026.html, site/sitemap.xml and site/robots.txt are up to date with
site/compare/tools.toml and site/site.toml, every row has its arrow and sources, the page sells nothing,
and the home and developers pages link it."""

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import compare_page  # noqa: E402


def test_outputs_are_up_to_date():
    for path, text in compare_page.outputs().items():
        assert path.is_file() and path.read_text(encoding="utf-8") == text, f"run `make compare` ({path.name})"


def test_every_tool_has_a_row_with_its_arrows_and_sources():
    text = compare_page.PAGE.read_text(encoding="utf-8")
    data = compare_page.tools()
    for key, tool in data["tools"].items():
        assert f'<tr id="{key}">' in text, key
        for arrow in tool["arrows"]:
            assert arrow.partition(" (")[0] in text, (key, arrow)
        for url in tool["sources"]:
            assert f'href="{url}"' in text, (key, url)


def test_site_url_lives_in_site_toml_alone():
    url = tomllib.loads(compare_page.SITE_TOML.read_text(encoding="utf-8"))["url"]
    assert url not in compare_page.Path(compare_page.__file__).read_text(encoding="utf-8")
    text = compare_page.PAGE.read_text(encoding="utf-8")
    assert f'<link rel="canonical" href="{url}{compare_page.PAGE_NAME}">' in text
    assert '"@type": "TechArticle"' in text and '"datePublished": "2026-11-20"' in text
    assert f"Sitemap: {url}sitemap.xml" in compare_page.ROBOTS.read_text(encoding="utf-8")


def test_sitemap_pages_exist():
    for loc in re.findall(r"<loc>([^<]+)</loc>", compare_page.SITEMAP.read_text(encoding="utf-8")):
        path = loc.removeprefix(compare_page.site()["url"]) or "index.html"
        if path.startswith("reference/"):
            continue  # written when the site is deployed
        assert (ROOT / "site" / path).is_file(), path


def test_page_is_not_commercial():
    text = (compare_page.PAGE.read_text(encoding="utf-8") + compare_page.TOOLS.read_text(encoding="utf-8")).lower()
    for word in ("packs.html", "superhive", "state-of-market", " pro ", "price"):
        assert word not in text, word


def test_home_and_developers_link_the_page():
    for page in ("index.html", "developers.html"):
        assert f'href="{compare_page.PAGE_NAME}"' in (ROOT / "site" / page).read_text(encoding="utf-8"), page
