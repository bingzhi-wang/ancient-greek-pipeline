# ==============================================================
# lsj_local.py  —  FIXED VERSION
# Run once to build lsj.db, then import lsj_lookup() into pipeline.py
#
# ROOT CAUSE OF EMPTY DEFINITIONS:
#   The Perseus XML stores Greek in Beta Code (lo/gos, yuxh/, nou=s).
#   The original build indexed the raw Beta Code keys, so Unicode
#   lookups (λόγος, ψυχή, νοῦς) never matched anything.
#
# FIX:
#   At build time, convert every Beta Code key → Unicode with the
#   beta_code library, so the DB is indexed in plain Unicode Greek.
#   The <tr> extraction is also corrected: TEI uses TEIform="tr"
#   attributes, so lxml's {*}tr wildcard namespace search is needed.
# ==============================================================
"""
Setup (run once):
    pip install lxml beta-code --break-system-packages
    python lsj_local.py
"""

import sqlite3, re, unicodedata
from lxml import etree
from pathlib import Path
import urllib.request
import beta_code                     # pip install beta-code

LSJ_DB   = Path("lsj.db")
LSJ_XML  = Path("lsj_combined.xml")
BASE_URL = (
    "https://raw.githubusercontent.com/PerseusDL/lexica/master/"
    "CTS_XML_TEI/perseus/pdllex/grc/lsj/"
)
N_FILES = 27


# ── 1. Download (unchanged) ────────────────────────────────────────────────

def download_lsj():
    if LSJ_XML.exists():
        print(f"  {LSJ_XML} already present, skipping download.")
        return
    print("Downloading LSJ XML files from PerseusDL GitHub...")
    entries_xml = []
    for i in range(1, N_FILES + 1):
        fname = f"grc.lsj.perseus-eng{i}.xml"
        print(f"  [{i:02d}/{N_FILES}] {fname}", end="\r")
        with urllib.request.urlopen(BASE_URL + fname, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")
        for m in re.finditer(r'<entryFree\b.*?</entryFree>', raw, re.DOTALL):
            entries_xml.append(m.group())
    print(f"\n  Collected {len(entries_xml):,} entries.")
    LSJ_XML.write_text("<lsj>\n" + "\n".join(entries_xml) + "\n</lsj>",
                       encoding="utf-8")
    print(f"  Written to {LSJ_XML}")


# ── 2. Beta Code → Unicode helpers ────────────────────────────────────────

def beta_to_unicode(s: str) -> str:
    """Convert a Beta Code string to Unicode Greek. Returns '' on failure."""
    if not s:
        return ""
    try:
        # Perseus uses lowercase beta code; uppercase entries start with *
        s = s.strip()
        return beta_code.beta_code_to_greek(s)
    except Exception:
        return ""

def normalise(s: str) -> str:
    """Strip all combining diacritics, lowercase — for fallback matching."""
    s = unicodedata.normalize("NFC", s)
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    ).lower()


# ── 3. Extract <tr> translations from an entry element ────────────────────

def _text_of(el) -> str:
    parts = [el.text or ""]
    for child in el:
        parts.append(_text_of(child))
        parts.append(child.tail or "")
    return " ".join(p for p in parts if p.strip())

def extract_translations(entry_el) -> str:
    """
    Collect <tr> elements (the English gloss lines in LSJ TEI).
    TEI uses TEIform="tr" as an attribute, not a namespace —
    so we search by local-name to be namespace-safe.
    """
    # lxml xpath with local-name() handles any namespace or no-namespace
    trs = entry_el.xpath(".//*[local-name()='tr']")
    if trs:
        glosses = []
        for tr in trs:
            t = _text_of(tr).strip()
            # Skip very short noise tokens and pure punctuation
            if t and len(t) > 1 and any(c.isalpha() for c in t):
                glosses.append(t)
        if glosses:
            return "; ".join(dict.fromkeys(glosses))

    # Fallback: full plain text of entry, capped at 500 chars
    # The raw text may contain Beta Code fragments — convert them
    raw = _text_of(entry_el)
    raw = re.sub(r'\s{2,}', ' ', raw).strip()
    # Convert any remaining Beta Code tokens (contain / = * ( ) chars)
    def _bc_token(m):
        converted = beta_to_unicode(m.group(0))
        return converted if converted else m.group(0)
    raw = re.sub(r'[a-z*/)(=\\|+\']+(?:[/=\\|+\'][a-z*/)(=\\|+\']*)+', _bc_token, raw)
    return raw[:500]


# ── 4. Build SQLite (FIXED: index by Unicode, not Beta Code) ──────────────

def build_db():
    # Always rebuild so the fix takes effect
    if LSJ_DB.exists():
        LSJ_DB.unlink()
        print("  Removed old lsj.db — rebuilding with Unicode keys.")

    print("Parsing XML and building SQLite database...")
    tree  = etree.parse(str(LSJ_XML))
    root  = tree.getroot()

    con = sqlite3.connect(LSJ_DB)
    con.execute("""
        CREATE TABLE entries (
            key     TEXT PRIMARY KEY,
            lemma   TEXT,
            defn    TEXT
        )
    """)
    con.execute("CREATE INDEX idx_key   ON entries(key)")
    con.execute("CREATE INDEX idx_strip ON entries(key)")   # same column, helps LIKE

    rows = {}   # key → (lemma_unicode, defn)  — dict deduplicates

    for entry in root.findall("entryFree"):
        beta_key = entry.get("key", "")
        defn     = extract_translations(entry)
        if not defn:
            continue

        # Convert Beta Code key to Unicode
        uni_key   = beta_to_unicode(beta_key)
        uni_strip = normalise(uni_key) if uni_key else ""

        # Also grab the <orth> headword (already Unicode in PerseusDL files)
        orth_el   = entry.find(".//*[@TEIform='orth']")
        orth_text = _text_of(orth_el).strip() if orth_el is not None else ""
        orth_strip = normalise(orth_text) if orth_text else ""

        lemma_display = orth_text or uni_key

        # Store up to three keys pointing to same definition
        for k in filter(None, dict.fromkeys([
            uni_key.lower(),
            uni_strip,
            orth_text.lower(),
            orth_strip,
        ])):
            if k and k not in rows:
                rows[k] = (lemma_display, defn)

    con.executemany(
        "INSERT OR IGNORE INTO entries VALUES (?,?,?)",
        [(k, v[0], v[1]) for k, v in rows.items()]
    )
    con.commit()
    con.close()
    print(f"  Stored {len(rows):,} index rows in {LSJ_DB}")


# ── 5. Lookup (unchanged interface, now actually finds entries) ────────────

_lsj_con = None

def _get_con():
    global _lsj_con
    if _lsj_con is None:
        if not LSJ_DB.exists():
            raise FileNotFoundError(
                f"{LSJ_DB} not found — run lsj_local.py first."
            )
        _lsj_con = sqlite3.connect(LSJ_DB, check_same_thread=False)
    return _lsj_con

# ── Cross-reference resolver ───────────────────────────────────────────────

# Matches patterns like:
#   "v. no/os"  /  "see λόγος"  /  "v. lo/gos, ou=s"  /  "vid. no/os"
#   "nou=s , o( , v. no/os."  ← xref is mid-string, NOT at start
_XREF_RE = re.compile(
    r'(?:v\.|vid\.|see|cf\.)\s+([^\s,;\.]+)',   # NOTE: no ^ anchor
    re.IGNORECASE
)

def _resolve_xref(defn: str) -> str | None:
    """
    If defn contains a cross-reference anywhere ('v. no/os'), return the
    target lemma in Unicode. Otherwise return None.
    Uses re.search (not re.match) so it finds 'v.' mid-string too.
    """
    m = _XREF_RE.search(defn)           # search, not match
    if not m:
        return None
    target = m.group(1).strip()
    # Target may still be Beta Code (no/os) or already Unicode (νόος)
    if any(c in target for c in "/()*=\\|+'"):   # Beta Code punctuation chars
        target = beta_to_unicode(target)
    return target or None


def lsj_lookup(lemma: str) -> tuple[str, str]:
    """
    Look up a Greek lemma in the local LSJ SQLite database.
    Automatically follows one level of cross-reference ('v. νόος' → look up νόος).
    Returns (definition_text, '').
    """
    con = _get_con()

    def _query(key: str) -> str | None:
        row = con.execute(
            "SELECT defn FROM entries WHERE key = ?", (key,)
        ).fetchone()
        return row[0].strip() if row and row[0].strip() else None

    def _lookup_normalised(lemma: str) -> str | None:
        for key in dict.fromkeys([
            lemma.lower(),
            lemma.lower().replace("ς", "σ"),
            normalise(lemma),
        ]):
            result = _query(key)
            if result:
                return result
        return None

    defn = _lookup_normalised(lemma)
    if not defn:
        return "", ""

    # Follow cross-reference one level deep
    target = _resolve_xref(defn)
    if target:
        resolved = _lookup_normalised(target)
        if resolved and not _resolve_xref(resolved):  # don't chain infinitely
            return resolved, ""

    return defn, ""

# ── 6. Combined lookup for pipeline.py ────────────────────────────────────

def lookup_definition(lemma: str) -> tuple[str, str]:
    """Wiktionary first (has examples), LSJ fallback."""
    try:
        from pipeline import wiktionary_lookup
        defn, example = wiktionary_lookup(lemma)
        if defn.strip():
            return defn, example
    except ImportError:
        pass
    defn, _ = lsj_lookup(lemma)
    return defn, ""


# ── 7. Entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    download_lsj()
    build_db()

    print("\nSanity check:")
    for test in ["λόγος", "ψυχή", "νοῦς", "ἀρετή", "εἶδος"]:
        defn, _ = lsj_lookup(test)
        preview = defn[:100].replace("\n", " ") if defn else "— NOT FOUND —"
        print(f"  {test}: {preview}")