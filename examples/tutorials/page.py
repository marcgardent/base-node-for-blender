"""Write the page of each tutorial, site/tutorials/<name>.html, from its folder's page.html and step files.

  python3 examples/tutorials/page.py                   # write the pages
  python3 examples/tutorials/page.py --check           # fail if a page is not up to date
  python3 examples/tutorials/page.py toon_lights ...   # write (or check) these tutorials' pages alone

A tutorial is a folder of this one with a page.html: lunar_ground/ writes lunar-ground.html. Without
names, the pages written are those site/tutorials/ already has: the packs' tutorials have their folder
here but their page in the private studio, which lays its pages over this repository. Name a new
tutorial to write its first page.
`{{code step2_crater.bn crater_profile lunar_ground}}` becomes a <bn-view> of the whole file, its code beside
its nodes, open on the first graph named (the others are in its menu); `{{file step2_crater.bn}}` becomes a
<bn-file>, the file as a card to drag onto Blender. A page shows the files its folder's render.py builds,
and nothing else.
"""

import html
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE.parents[1] / "site" / "tutorials"
HEIGHT = 480  # px, of each <bn-view>


def graph(source, name, filename):
    """The text of one graph of a file: from its declaration to the `}` that closes it."""
    match = re.search(
        r"^(?:\w+(?:\([^)]*\))? )?graph " + re.escape(name) + r"\(.*?^\}$", source, re.S | re.M)
    if not match:
        raise SystemExit(f"{filename}: no graph {name}")
    return match.group(0)


def render(folder):
    template = (folder / "page.html").read_text(encoding="utf-8")

    def code(match):
        filename, *names = match.group(1).split()
        source = (folder / filename).read_text(encoding="utf-8")
        for name in names:
            graph(source, name, filename)  # a name the file does not have stops here
        assert "</script" not in source, f"{filename} would close the <script> that holds it"
        shown = ", ".join(f"<code>{html.escape(n)}</code>" for n in names)
        return (
            f'<p class="file">{html.escape(filename)}: {shown}</p>\n'
            f'    <bn-view graph="{html.escape(names[0])}" height="{HEIGHT}"><script type="text/bn">\n'
            f"{source}</script></bn-view>"
        )

    def card(match):
        filename = match.group(1).strip()
        source = (folder / filename).read_text(encoding="utf-8")
        assert "</script" not in source, f"{filename} would close the <script> that holds it"
        return f'<bn-file><script type="text/bn">\n{source}</script></bn-file>'

    page = re.sub(r"\{\{code ([^}]+)\}\}", code, template)
    return re.sub(r"\{\{file ([^}]+)\}\}", card, page)


def page_of(folder):
    """site/tutorials/<name>.html, the page of the tutorial `folder`."""
    return SITE / (folder.name.replace("_", "-") + ".html")


def pages(names=()):
    """{page: its text} of the tutorials named, else of those whose page site/tutorials/ has."""
    folders = [HERE / name for name in names] or [
        p.parent for p in HERE.glob("*/page.html") if page_of(p.parent).exists()]
    for folder in folders:
        if not (folder / "page.html").is_file():
            raise SystemExit(f"no tutorial {folder.name}: no {folder / 'page.html'}")
    return {page_of(folder): render(folder) for folder in sorted(folders)}


def main():
    check = "--check" in sys.argv
    for out, page in pages([a for a in sys.argv[1:] if a != "--check"]).items():
        if check:
            if not out.exists() or out.read_text(encoding="utf-8") != page:
                raise SystemExit(f"{out} is not up to date: run python3 examples/tutorials/page.py")
            print(f"{out.name} is up to date")
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
