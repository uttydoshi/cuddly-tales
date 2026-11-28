"""Writes docs/architecture.svg and docs/story-flow.svg from the inline drawings in docs/architecture.html,
with the page's colours (light, and dark via prefers-color-scheme) and the SVG part styles embedded.

    python3 scripts/export-diagrams.py docs
"""
import re, sys, pathlib
docs = pathlib.Path(sys.argv[1])
html = (docs / "architecture.html").read_text()
css = html[html.index("/* SVG parts"):html.index("</style>")]
light = "--bg:#ffffff;--fg:#1b2230;--muted:#5d6676;--line-strong:#8a93a3;--accent:#b86e0a;--accent-soft:#fbefd9;--accent-ink:#8a5207;--surface:#ffffff"
dark = "--bg:#18202c;--fg:#e4e8ef;--muted:#98a2b3;--line-strong:#5b6678;--accent:#f2b35a;--accent-soft:#2d2416;--accent-ink:#f2b35a;--surface:#18202c"
fonts = '--font-head:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;--font-body:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;--font-mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace'
style = f"<style>svg{{{light}}}@media (prefers-color-scheme: dark){{svg{{{dark}}}}}svg{{{fonts}}}.bg{{fill:var(--bg)}}{css}</style>"
svgs = re.findall(r"<svg viewBox=\"0 0 (\d+) (\d+)\"(.*?)>(.*?)</svg>", html, re.S)
for (w, h, attrs, body), name in zip(svgs, ["architecture.svg", "story-flow.svg"]):
    out = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"{attrs}>\n'
           f"          {style}\n          <rect class=\"bg\" width=\"{w}\" height=\"{h}\" rx=\"12\"/>{body}</svg>\n")
    (docs / name).write_text(out)
    print(name, w, h, len(out))
