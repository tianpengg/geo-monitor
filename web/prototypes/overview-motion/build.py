"""Embed local preview assets into one offline HTML. No third-party dependencies."""

import base64
import json
from pathlib import Path


def data_url(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def main() -> None:
    root = Path(__file__).resolve().parent
    assets = root / "assets"
    icons = {path.stem: path.read_text(encoding="utf-8") for path in sorted(assets.glob("*.svg"))}
    required = {"chart-bar", "file-text", "activity", "settings", "world", "x"}
    if not required.issubset(icons):
        raise SystemExit("Required local icons are missing")
    source = (root / "source.html").read_text(encoding="utf-8")
    rendered = (
        source.replace("__ICONS_JSON__", json.dumps(icons, ensure_ascii=False))
        .replace("__FONT_DATA__", data_url(assets / "InterVariable.woff2", "font/woff2"))
    )
    license_text = (assets / "tabler-LICENSE.txt").read_text(encoding="utf-8")
    font_license = (assets / "Inter-LICENSE.txt").read_text(encoding="utf-8")
    rendered = rendered.replace(
        "</head>",
        "<!--\nBundled assets: Tabler Icons v3.35.0\n"
        + license_text.replace("--", "—")
        + "\nInter v4.1\n"
        + font_license.replace("--", "—")
        + "\n-->\n</head>",
    )
    output = root / "index.html"
    output.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"Built {output} ({output.stat().st_size:,} bytes); all runtime assets embedded")


if __name__ == "__main__":
    main()
