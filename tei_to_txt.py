"""
tei_to_txt.py
-------------
Convert First1KGreek / Perseus TEI XML into clean plain text that the
Ancient Greek vocabulary pipeline can read.

TEI files wrap the Greek in tags and mix in editorial apparatus, notes,
page breaks, and metadata. Feeding that raw into the pipeline produces
garbage, so this script keeps only the running Greek text of the <body>
and drops the editorial scaffolding.

Usage
-----
Single file:
    python tei_to_txt.py --input sources/hippocrates/tlg001_De_prisca_medicina.xml \
                         --output book.txt

Whole folder (batch): every .xml in --input becomes a .txt in --output:
    python tei_to_txt.py --input sources/hippocrates --output sources/txt

Then run the pipeline on a converted file:
    python cli.py --input sources/txt/tlg001_De_prisca_medicina.txt \
                  --output vocab_tlg001.csv --no-llm

Requires lxml:  pip install lxml
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

try:
    from lxml import etree
except ImportError:
    sys.exit("This script needs lxml. Install it with:\n    pip install lxml")


# Elements removed entirely (their tail text — the words that follow them —
# is preserved). This strips editorial apparatus and non-text scaffolding:
#   note/bibl/ref  -> footnotes, citations, cross-references
#   rdg            -> apparatus variant readings (the main reading is in <lem>)
#   sic/abbr/orig  -> the *un*corrected half of a <choice>; we keep corr/expan/reg
#   pb/lb/milestone/gap/figure/figDesc/fw -> page & line breaks, figures, running heads
#   teiHeader      -> file metadata (also excluded by only reading <body>, belt-and-braces)
DROP_TAGS = [
    "note", "bibl", "ref", "rdg",
    "sic", "abbr", "orig",
    "pb", "lb", "milestone", "gap", "figure", "figDesc", "fw", "label",
    "teiHeader",
]


def strip_namespaces(root):
    """TEI tags come namespaced (e.g. '{http://www.tei-c.org/ns/1.0}p').
    Rename every tag to its local name so we can match on plain names."""
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    etree.cleanup_namespaces(root)


def normalize_ws(text):
    """NFC-normalise, collapse whitespace, tidy spaces before punctuation."""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", " ", text)
    # no space before Greek/Latin punctuation, incl. ano teleia (·) and ; (Greek '?')
    text = re.sub(r"\s+([,.;··:!?])", r"\1", text)
    return text.strip()


def convert_tree(root):
    strip_namespaces(root)
    etree.strip_elements(root, *DROP_TAGS, with_tail=False)

    body = root.find(".//body")
    if body is None:                       # some files nest differently
        body = root.find(".//text")
    if body is None:
        return ""

    return normalize_ws(" ".join(body.itertext()))


def convert_file(inp: Path, outp: Path) -> int:
    # recover=True tolerates the occasional malformed entity these files have
    parser = etree.XMLParser(recover=True)
    tree = etree.parse(str(inp), parser)
    text = convert_tree(tree.getroot())
    outp.write_text(text, encoding="utf-8")
    return len(text)


def main():
    ap = argparse.ArgumentParser(
        description="Convert TEI XML (First1KGreek/Perseus) to clean plain text."
    )
    ap.add_argument("--input", "-i", required=True,
                    help="A .xml file, or a folder of .xml files.")
    ap.add_argument("--output", "-o", required=True,
                    help="Output .txt file (single input) or output folder (folder input).")
    args = ap.parse_args()

    inp = Path(args.input)
    outp = Path(args.output)

    if not inp.exists():
        sys.exit(f"Input not found: {inp}")

    if inp.is_dir():
        outp.mkdir(parents=True, exist_ok=True)
        xmls = sorted(inp.glob("*.xml"))
        if not xmls:
            sys.exit(f"No .xml files found in {inp}")
        total = 0
        for x in xmls:
            dest = outp / (x.stem + ".txt")
            try:
                n = convert_file(x, dest)
            except Exception as exc:
                print(f"  FAILED {x.name}: {exc}")
                continue
            flag = "  ⚠ very short — check this file" if n < 200 else ""
            print(f"{x.name} → {dest.name}  ({n} chars){flag}")
            total += 1
        print(f"\nConverted {total} file(s) into {outp}/")
    else:
        # single file: if --output looks like a folder, put <stem>.txt inside it
        if outp.is_dir() or str(args.output).endswith(("/", "\\")):
            outp.mkdir(parents=True, exist_ok=True)
            dest = outp / (inp.stem + ".txt")
        else:
            dest = outp
            if dest.parent and not dest.parent.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
        n = convert_file(inp, dest)
        flag = "  ⚠ very short — check this file" if n < 200 else ""
        print(f"{inp.name} → {dest}  ({n} chars){flag}")


if __name__ == "__main__":
    main()
