"""Builds assets/spartito-s1.js: prelude.js + spartito.js (Miki's, as it is in B:\\Spartito) + glue.js.

spartito.js is copied unchanged except for the sentences below, which speak of
Live where Studio One is meant. Each must be found exactly once, so a newer
spartito.js that no longer has one of them stops the build instead of drifting.
"""
import pathlib, sys

HERE = pathlib.Path(__file__).parent
PATCHES = [
    ('"Click a MIDI clip in Live, or click on a staff to write. Every change goes straight into the clip."',
     '"Play with REC on, or click on a staff to write. The score is saved with the song."'),
    ('"Trill on the selected note (again: remove it). Live plays it"',
     '"Trill on the selected note (again: remove it). The MIDI export plays it"'),
]

def main():
    src = (HERE / "spartito.js").read_text(encoding="utf-8")
    for old, new in PATCHES:
        n = src.count(old)
        if n != 1:
            sys.exit(f"build.py: expected 1 of {old!r}, found {n}")
        src = src.replace(old, new)
    out = (HERE / "prelude.js").read_text(encoding="utf-8") + "\n" + src + "\n" + (HERE / "glue.js").read_text(encoding="utf-8")
    dst = HERE.parent / "assets" / "spartito-s1.js"
    dst.write_text(out, encoding="utf-8")
    print(f"{dst}: {len(out)} chars")

if __name__ == "__main__":
    main()
