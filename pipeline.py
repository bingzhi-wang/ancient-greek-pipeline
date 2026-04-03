import re
import csv
import json
import time
import urllib.request as _urllib_req
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from cltk import NLP
from urllib.parse import quote
from lsj_local import lsj_lookup

# --------------------------------------------------
# BASIC SETTINGS
# --------------------------------------------------
INPUT_TEXT  = "book.txt"
OUTPUT_CSV  = "vocab.csv"

# Load the Ancient Greek NLP pipeline from CLTK
nlp = NLP(language_code="grc", suppress_banner=True)

# --------------------------------------------------
# STOPWORDS
# Function words useless as vocabulary cards.
# --------------------------------------------------
GRC_STOPWORDS = {
    "ὁ", "ἡ", "τό", "οἱ", "αἱ", "τά",
    "καί", "δέ", "γάρ", "ἀλλά", "οὖν", "μέν", "τε", "ἄν",
    "ὅτι", "εἰ", "ὡς", "ἤ", "ἵνα", "ὅταν", "ἐάν", "ὅτε",
    "ἆρα", "ἄρα", "νῦν", "ἤδη", "ἔτι", "πάλιν",
    "οὐ", "οὐκ", "οὐχ", "μή", "οὐδέ", "μηδέ",
    "οὔτε", "μήτε", "οὐδείς", "μηδείς",
    "ἐν", "εἰς", "ἐκ", "ἐξ", "ἐπί", "ἀπό", "πρός",
    "διά", "κατά", "μετά", "παρά", "περί", "ὑπό",
    "ὑπέρ", "ἀντί", "ἀνά", "σύν",
    "αὐτός", "αὐτή", "αὐτό", "οὗτος", "αὕτη", "τοῦτο",
    "ἐκεῖνος", "ὅς", "ἥ", "ὅ", "τίς", "τί", "τις", "τι",
    "ἐγώ", "σύ", "ἡμεῖς", "ὑμεῖς",
    "οὕτως", "οὕτω", "ὥσπερ", "ὁμοίως", "μάλιστα",
    # Modern Greek stopwords (text is in modern Greek translation)
    "και", "δεν", "την", "των", "της", "του", "τα", "τον",
    "με", "για", "απο", "ειναι", "που", "ως", "αν", "η",
    "οχι", "μας", "το", "πρεπει", "μονη", "του", "εις",
    "την", "πολλα", "αλλα", "μετα", "αυτα", "εαν", "εχει",
    "απο", "προς", "δια", "επι", "παρα", "περι", "υπο",
    "πρωτον", "δε", "γαρ", "αλλα", "μεν", "τε", "αν",
    "ει", "ηδη", "ετι", "διαφορος", "ετερων", "ελληνικα",
}

# --------------------------------------------------
# Special characters forbidden in word/lemma fields
# --------------------------------------------------
SPECIAL_CHARS = set("()/\\|=+*'")

# --------------------------------------------------
# STEP 1 — Load and clean the book text
# --------------------------------------------------
def clean_book_text(text):
    """Strip markup. Uses line-by-line *** toggle to avoid swallowing
    ΒΙΒΛΙΟΝ headings that sit adjacent to unclosed footnote blocks."""
    text = text.replace('\r\n', '\n')

    _HEADING_RE = re.compile(
        r'^[ \t]*(ΒΙΒΛΙΟΝ\s+\w+|ΚΕΦΑΛΑΙΟΝ\s+\w+)', re.UNICODE
    )
    in_block = False
    kept_lines = []
    for line in text.split('\n'):
        if line.strip() == '***':
            in_block = not in_block
            continue
        if in_block and not _HEADING_RE.match(line):
            continue
        kept_lines.append(line)
    text = '\n'.join(kept_lines)

    text = re.sub(r'\{[^}]*\}', '', text)            # footnote refs
    text = re.sub(r'&&.*?&&', '', text, flags=re.DOTALL)  # chapter summaries
    text = re.sub(r'//', '', text)                    # editor markers
    text = re.sub(r'(?<![&])&(?![&])', '', text)     # stray & from && blocks
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def load_text(file):
    with open(file, 'r', encoding='utf-8') as f:
        raw = f.read()
    return clean_book_text(raw)

# --------------------------------------------------
# STEP 2 — Split text into chapters
# --------------------------------------------------
CHAPTER_PATTERN = re.compile(
    r"(?m)^[ \t]*("
    r"ΒΙΒΛΙΟΝ\s+\w+"
    r"|ΚΕΦΑΛΑΙΟΝ\s+[ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩςϚ]+'?\.?"
    r")[ \t]*$",
    re.UNICODE
)

def find_book_headings(text):
    """Diagnostic: find all ΒΙΒΛΙΟΝ occurrences regardless of format."""
    print("  Diagnostic — all ΒΙΒΛΙΟΝ occurrences in text:")
    for m in re.finditer(r'ΒΙΒΛΙΟΝ\s+\S+', text, re.UNICODE):
        start = max(0, m.start() - 20)
        end   = min(len(text), m.end() + 20)
        print(f"    {repr(text[start:end])}")

def split_chapters(text):
    """Return list of (chapter_label, text) tuples."""
    boundaries = [(m.start(), m.group().strip()) for m in CHAPTER_PATTERN.finditer(text)]

    if not boundaries:
        print("  Warning: no chapter headings detected — treating as single text.")
        return [("Full Text", text)]

    print(f"  All boundaries found ({len(boundaries)}):")
    for _, label in boundaries:
        print(f"    {repr(label)}")

    chapters = []
    current_book = ""
    for i, (start, label) in enumerate(boundaries):
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
        if label.startswith("ΒΙΒΛΙΟΝ"):
            current_book = label
            body = text[start:end].strip()[len(label):].strip()
            if body:
                chapters.append((f"{current_book} — intro", body))
        else:
            full_label = f"{current_book} — {label}" if current_book else label
            chapters.append((full_label, text[start:end]))
    return chapters

# --------------------------------------------------
# STEP 3 — CLTK Greek analysis
# --------------------------------------------------
def analyze_greek(text):
    doc = nlp.analyze(text)
    tokens = []
    for sentence in doc.sentences:
        sentence_text = " ".join(w.string for w in sentence.words if w.string)
        for word in sentence.words:
            if word.lemma is None:
                continue
            if all(not c.isalpha() for c in word.lemma):
                continue
            # Extract POS tag string cleanly
            pos = ""
            if word.upos:
                pos = word.upos.tag if hasattr(word.upos, "tag") else str(word.upos)
            tokens.append({
                "word":     word.string,
                "lemma":    word.lemma,
                "pos":      pos,
                "sentence": sentence_text,
            })
    return tokens

# --------------------------------------------------
# STEP 4 — Deduplicate with stopword filter + LSJ
#           lemma validation
# --------------------------------------------------
def _trim_definition(defn: str, max_senses: int = 3) -> str:
    """Keep only the first max_senses numbered lines from LSJ output."""
    if not defn:
        return defn
    lines = defn.split("\n")
    numbered = [l for l in lines if re.match(r'^\s*\d+\.', l)]
    if not numbered:
        return defn[:300].rstrip() + ("…" if len(defn) > 300 else "")
    kept = numbered[:max_senses]
    if len(numbered) > max_senses:
        kept.append(f"  … ({len(numbered) - max_senses} more senses in LSJ)")
    return "\n".join(kept)

def _stopword_set():
    """Pre-compute a set of NFC-normalized stopwords plus their base-form
    (accent-stripped) variants for fast single-lookup comparison."""
    import unicodedata as _ud
    result = set()
    for sw in GRC_STOPWORDS:
        sw_nfc = _ud.normalize("NFC", sw)
        result.add(sw_nfc.lower())
        sw_flat = _ud.normalize("NFD", sw_nfc)
        sw_base = "".join(c for c in sw_flat if _ud.category(c) != "Mn")
        # NFC-recompose so same encoding is used for lookups
        result.add(_ud.normalize("NFC", sw_base).lower())
    return result

_STOPWORD_BASES = _stopword_set()

def _is_stopword(lemma: str) -> bool:
    """Check if lemma is a stopword, using NFC normalization."""
    import unicodedata as _ud
    lemma_nfc = _ud.normalize("NFC", lemma)
    if lemma_nfc.lower() in _STOPWORD_BASES:
        return True
    # Strip combining marks for base-form check
    lemma_flat = _ud.normalize("NFD", lemma_nfc)
    lemma_base = "".join(c for c in lemma_flat if _ud.category(c) != "Mn")
    lemma_base = _ud.normalize("NFC", lemma_base).lower()
    return lemma_base in _STOPWORD_BASES


def validate_token(lemma: str, word: str) -> bool:
    """Return False if lemma or word contains forbidden special characters."""
    if any(c in SPECIAL_CHARS for c in lemma):
        return False
    if any(c in SPECIAL_CHARS for c in word):
        return False
    # Reject lemmas that are mostly non-alpha (punctuation-only)
    if all(not c.isalpha() for c in lemma):
        return False
    return True


def deduplicate(tokens):
    """Deduplicate by lemma, skipping stopwords, validating against LSJ,
    and filtering tokens with forbidden special characters.

    Discards any lemma that has no LSJ entry AND no surface form with an
    LSJ entry — this eliminates CLTK garbage lemmas from modern Greek text.
    """
    seen = {}
    for token in tokens:
        lemma = token["lemma"]
        if not lemma:
            continue
        word = token.get("word", "")
        # Stopword filter
        if _is_stopword(lemma):
            continue
        # Special-char filter
        if not validate_token(lemma, word):
            continue
        if lemma not in seen:
            # LSJ validation: if CLTK lemma has no entry, try surface form
            defn, _ = lsj_lookup(lemma)
            if not defn:
                surface = token.get("word", "")
                if surface and surface != lemma and validate_token(surface, surface):
                    surface_defn, _ = lsj_lookup(surface)
                    if surface_defn:
                        token = dict(token)
                        token["lemma"] = surface
                        lemma = surface
                        defn = surface_defn
                    # If neither lemma nor surface has LSJ entry, skip entirely
                    else:
                        continue
            if lemma not in seen:
                seen[lemma] = token
    return list(seen.values())

# --------------------------------------------------
# STEP 5 — Definition lookup: Wiktionary → LSJ
# --------------------------------------------------
HEADERS = {"User-Agent": "GreekVocabPipeline/1.0 (educational use)"}

STOP_SECTIONS = {
    "Etymology", "Etymology_1", "Etymology_2", "Pronunciation",
    "Declension", "Conjugation", "Inflection", "Derived_terms",
    "Descendants", "Related_terms", "See_also", "Synonyms",
    "Antonyms", "References", "Further_reading",
}
DEFINITION_SECTIONS = {
    "Noun", "Verb", "Adjective", "Adverb", "Preposition",
    "Conjunction", "Particle", "Interjection", "Pronoun",
    "Numeral", "Article", "Determiner",
}

def clean(text):
    text = re.sub(r'\s*\^+\s*', '', text)
    text = re.sub(r'\[\d+\]', '', text)
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'\s+\)', ')', text)
    text = re.sub(r'\s+([,;:!?.])', r'\1', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

def get_heading_id(div):
    h = div.find(re.compile(r'^h[2-6]$'))
    if not h:
        return ""
    span = h.find("span", class_="mw-headline")
    if span and span.get("id"):
        return span["id"]
    return h.get("id", "")

def is_citation_ul(ul):
    signals = ["ISBN", "Brill", "Leiden", "Boston", "ISSN", "Oxford", "Cambridge"]
    return any(s in ul.get_text() for s in signals)

def parse_ol(ol, indent=0):
    lines = []
    pad = "  " * indent
    for i, li in enumerate(ol.find_all("li", recursive=False), 1):
        li_clone = BeautifulSoup(str(li), "html.parser").find("li")
        for nested in li_clone.find_all(["ol", "ul"]):
            nested.decompose()
        meaning = clean(li_clone.get_text(" ", strip=True))
        if meaning:
            lines.append(f"{pad}{i}. {meaning}")
        orig = BeautifulSoup(str(li), "html.parser").find("li")
        sub_ol = orig.find("ol")
        if sub_ol:
            lines.extend(parse_ol(sub_ol, indent + 1))
        for sub_ul in orig.find_all("ul", recursive=False):
            if is_citation_ul(sub_ul):
                continue
            for ex_li in sub_ul.find_all("li", recursive=False):
                ex = clean(ex_li.get_text(" ", strip=True))
                if ex:
                    lines.append(f"{pad}  • {ex}")
    return lines

def get_ancient_greek_blocks(soup):
    blocks = []
    in_greek = False
    container = soup.find(class_="mw-parser-output")
    if not container:
        return blocks
    for child in container.children:
        if not hasattr(child, "get"):
            continue
        cls_str = " ".join(child.get("class", []))
        if "mw-heading2" in cls_str:
            if in_greek:
                break
            if child.find(id="Ancient_Greek"):
                in_greek = True
            continue
        if in_greek:
            blocks.append(child)
    return blocks

def wiktionary_lookup(lemma):
    """Return (definition_text, example_text) or ('', '') on miss."""
    try:
        url = (
            f"https://en.wiktionary.org/w/api.php"
            f"?action=parse&page={quote(lemma)}&prop=text&format=json"
        )
        raw_html = requests.get(url, headers=HEADERS, timeout=10).json()["parse"]["text"]["*"]
        soup   = BeautifulSoup(raw_html, "html.parser")
        blocks = get_ancient_greek_blocks(soup)
        if not blocks:
            return "", ""
        lines, examples = [], []
        render = False
        for block in blocks:
            cls_str = " ".join(block.get("class", []))
            if "mw-heading" in cls_str:
                sid = get_heading_id(block)
                render = (
                    any(s in sid for s in DEFINITION_SECTIONS)
                    and not any(s in sid for s in STOP_SECTIONS)
                )
                continue
            if not render:
                continue
            if block.name == "p":
                t = clean(block.get_text(" ", strip=True))
                if "•" in t:
                    lines.append(t)
            elif block.name == "ol":
                ol_lines = parse_ol(block)
                lines.extend(ol_lines)
                examples.extend([l.strip().lstrip("•").strip() for l in ol_lines if "•" in l])
            elif block.name == "ul" and not is_citation_ul(block):
                for li in block.find_all("li", recursive=False):
                    t = clean(li.get_text(" ", strip=True))
                    if t:
                        lines.append(f"  • {t}")
        return "\n".join(lines), "\n".join(examples[:3])
    except Exception:
        return "", ""

# --------------------------------------------------
# STEP 5b — Definition cleaning
# --------------------------------------------------
_MAX_DEF = 600
_MAX_SENSE = 120
_XREF_RE = re.compile(
    r'\b(?:v\.|vid\.|see\b|cf\.|Compare)\s+\w+',
)
def clean_definition(defn: str) -> str:
    """Strip markup artifacts, cap length, remove cross-refs."""
    if not defn or not defn.strip():
        return ""
    t = defn
    # 1. Strip caret markers
    t = re.sub(r'\s*\^+\s*', ' ', t)
    # 2. Strip citation brackets
    t = re.sub(r'\[\d+\]', '', t)
    # 3. Strip LSJ cross-references
    t = _XREF_RE.sub('', t)
    # 4. Collapse consecutive newlines
    t = re.sub(r'\n{3,}', '\n\n', t)
    # 5. Collapse repeated whitespace on each line
    t = '\n'.join(
        re.sub(r' {2,}', ' ', line).strip()
        for line in t.splitlines()
    )
    # 6. Flatten numbered senses: keep only first 3
    numbered = re.findall(r'^(\s*\d+\.\s.*)$', t, re.MULTILINE)
    if len(numbered) > 3:
        t = '\n'.join(l.strip() for l in numbered[:3])
    # 7. Soft cap
    if len(t) > _MAX_DEF:
        t = t[: _MAX_DEF - 3].rstrip() + '...'
    return t.strip()


def post_validate(entries: list) -> list:
    """Filter invalid entries and clean all text fields."""
    valid = []
    for e in entries:
        lemma = e.get('lemma', '')
        word = e.get('word', '')
        # Reject special-character entries
        if not validate_token(lemma, word):
            continue
        # Stopword check (post-enrich catch)
        if _is_stopword(lemma):
            continue
        # Clean definition
        defn = clean_definition(e.get('definition', ''))
        sense = e.get('best_sense', '').strip()
        if len(sense) > _MAX_SENSE:
            sense = sense[: _MAX_SENSE - 3].rstrip() + '...'
        e['definition'] = defn
        e['best_sense'] = sense
        # Reject entirely empty entries
        if not any([
            defn.strip(),
            sense.strip(),
            e.get('example_grc', '').strip(),
        ]):
            continue
        valid.append(e)
    return valid



def lookup_definition(lemma):
    """Wiktionary first (has examples), local LSJ fallback."""
    defn, example = wiktionary_lookup(lemma)
    if defn.strip():
        return defn, example
    defn, _ = lsj_lookup(lemma)
    return _trim_definition(defn), ""

# --------------------------------------------------
# STEP 6 — Frequency analysis
# --------------------------------------------------
def build_frequency_table(all_tokens):
    from collections import Counter
    counts = Counter(t["lemma"] for t in all_tokens)
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    total  = len(ranked)
    table  = {}
    for rank, (lemma, count) in enumerate(ranked, start=1):
        pct = rank / total
        if   pct <= 0.05: tag = "core"
        elif pct <= 0.20: tag = "important"
        elif pct <= 0.50: tag = "uncommon"
        else:             tag = "rare"
        table[lemma] = {"count": count, "rank": rank, "tag": tag}
    return table

# --------------------------------------------------
# STEP 7a — Ollama / qwen3:4b enrichment
#
# Requires: ollama serve  +  ollama pull qwen3:4b
# Cache:    ollama_cache.json (crash-safe, resume on restart)
# --------------------------------------------------
OLLAMA_CACHE = "ollama_cache.json"
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3:4b"

_ollama_cache: dict = {}

def _load_cache():
    global _ollama_cache
    try:
        _ollama_cache = json.loads(open(OLLAMA_CACHE, encoding="utf-8").read())
    except FileNotFoundError:
        _ollama_cache = {}

def _save_cache():
    open(OLLAMA_CACHE, "w", encoding="utf-8").write(
        json.dumps(_ollama_cache, ensure_ascii=False, indent=2)
    )

def ollama_enrich(lemma: str, pos: str, raw_defn: str, context_sentence: str) -> dict:
    """
    Query local Ollama (qwen3:4b) for:
      - best_sense:  most relevant meaning for Aristotle's De Anima
      - example_grc: short classical Greek sentence using this word
      - example_eng: English translation of that sentence

    Returns empty strings if definition is missing or Ollama fails.
    Results cached to ollama_cache.json after every call.
    """
    cache_key = lemma
    if cache_key in _ollama_cache:
        return _ollama_cache[cache_key]

    empty = {"best_sense": "", "example_grc": "", "example_eng": ""}

    if not raw_defn.strip():
        _ollama_cache[cache_key] = empty
        return empty

    sense_list = raw_defn.strip()

    prompt = f"""
    You are a Classical Greek linguist.

    Task:
    Select the best sense of the lemma and produce ONE Classical Greek example sentence.

    Rules:
    - Return ONLY valid JSON
    - No explanations
    - No markdown
    - No comments
    - No thinking text
    - No extra text before or after JSON
    - If uncertain, still return valid JSON with empty fields

    Requirements:
    - example_grc must be Classical Greek (not Koine)
    - Write a short natural sentence (5–12 words)
    - example_eng must be an accurate translation
    - best_sense must be concise (under 12 words)

    Return EXACTLY this format:

    {{"best_sense":"definition",
    "example_grc":"greek sentence",
    "example_eng":"translation"}}

    Lemma:
    {lemma}

    Senses:
    {sense_list}

    Return ONLY the JSON.
    If generation fails return exactly:

    {{"best_sense":"",
    "example_grc":"",
    "example_eng":""}}
    """

    payload = json.dumps({
        "model":   OLLAMA_MODEL,
        "prompt":  prompt,
        "stream":  False,
        "format": "json",
        "options": {"temperature": 0.1, "num_predict": 400},
    }).encode("utf-8")

    text = ""
    try:
        req = _urllib_req.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _urllib_req.urlopen(req, timeout=180) as resp:
            raw_bytes = resp.read()
        data = json.loads(raw_bytes.decode("utf-8"))

        # qwen3 via Ollama puts the answer in "response" normally, but when
        # the thinking tokens overflow the context it puts everything in
        # "thinking" and leaves "response" empty.  So we check both fields
        # and scan for the first valid JSON object in whichever has content.
        candidates = [
            data.get("response", ""),
            data.get("thinking", ""),
        ]
        cleaned = ""

        for source in candidates:
            if not source:
                continue

            s = source.strip()

            # remove markdown
            s = re.sub(r"^```(?:json)?", "", s)
            s = re.sub(r"```$", "", s).strip()

            # direct JSON
            if s.startswith("{"):
                cleaned = s
                break

            # find JSON inside text
            m = re.search(r'\{.*?\}', s, re.DOTALL)
            if m:
                cleaned = m.group(0)
                break

        if not cleaned:
            result = empty
        else:
            try:
                result = json.loads(cleaned)
                result = {
                    "best_sense":  str(result.get("best_sense",  "")),
                    "example_grc": str(result.get("example_grc", "")),
                    "example_eng": str(result.get("example_eng", "")),
                }
            except json.JSONDecodeError as exc:
                print(f"    [Ollama JSON error for {lemma!r}: {exc} | raw: {text[:120]!r}]")
                result = empty
            except Exception as exc:
                print(f"    [Ollama error for {lemma!r}: {exc}]")
                result = empty

    except Exception as exc:
        print(f"    [Ollama request error for {lemma!r}: {exc}]")
        result = empty

    _ollama_cache[cache_key] = result
    _save_cache()
    return result

# --------------------------------------------------
# STEP 7 — Enrich tokens
# --------------------------------------------------
def enrich(entries, freq_table):
    """
    For each lemma:
      1. Look up definition via Wiktionary → local LSJ.
      2. Call Ollama (qwen3:4b) for best_sense + classical example.
      3. Cache Ollama results to ollama_cache.json after every call.
    """
    _load_cache()
    output = []
    for e in tqdm(entries):
        definition, wiki_example = lookup_definition(e["lemma"])
        freq    = freq_table.get(e["lemma"], {"count": 0, "rank": 0, "tag": "rare"})
        context = e.get("sentence", "")

        enriched = ollama_enrich(
            lemma            = e["lemma"],
            pos              = e.get("pos", ""),
            raw_defn         = definition,
            context_sentence = context,
        )

        output.append({
            "word":        e["word"],
            "lemma":       e["lemma"],
            "pos":         e.get("pos", ""),
            "definition":  definition,
            "best_sense":  enriched["best_sense"],
            "example_grc": enriched["example_grc"],
            "example_eng": enriched["example_eng"],
            "frequency":   freq["tag"],
            "count":       freq["count"],
            "rank":        freq["rank"],
            "example":     context,
            "chapter":     e.get("chapter", ""),
        })
        time.sleep(0.5)   # rate-limit Wiktionary; Ollama is local
    return output

# --------------------------------------------------
# STEP 8 — Write master CSV
# --------------------------------------------------
def write_csv(entries, path=OUTPUT_CSV):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "word", "lemma", "pos",
            "definition", "best_sense",
            "example_grc", "example_eng",
            "frequency", "count", "rank",
            "example", "chapter",
        ])
        for e in entries:
            writer.writerow([
                e.get("word", ""),       e.get("lemma", ""),  e.get("pos", ""),
                e.get("definition", ""), e.get("best_sense", ""),
                e.get("example_grc", ""),e.get("example_eng", ""),
                e.get("frequency", ""),  e.get("count", ""),  e.get("rank", ""),
                e.get("example", ""),    e.get("chapter", ""),
            ])

# --------------------------------------------------
# STEP 9 — Write per-chapter CSVs
# --------------------------------------------------
def write_chapter_csvs(entries):
    from collections import defaultdict
    by_chapter = defaultdict(list)
    for e in entries:
        by_chapter[e["chapter"]].append(e)
    for chapter, rows in by_chapter.items():
        safe = re.sub(r"[^\w\s-]", "", chapter).strip()
        safe = re.sub(r"\s+", "_", safe)
        path = f"vocab_{safe}.csv"
        write_csv(rows, path)
        print(f"  Wrote {path}  ({len(rows)} words)")

# --------------------------------------------------
# MAIN
# --------------------------------------------------
def main():
    print("Loading text...")
    text = load_text(INPUT_TEXT)

    find_book_headings(text)

    import re as _re
    found = _re.findall(r'(?m)^[ \t]*[ΒΚΜΠ][ΙΕΑΒΡ]\w+.*$', text)
    print(f"  Headings found in cleaned text ({len(found)}):")
    for h in found[:20]:
        print(f"    {repr(h)}")

    print("Splitting into chapters...")
    chapters = split_chapters(text)
    print(f"  Found {len(chapters)} chapter(s)")

    all_tokens = []
    print("Analyzing Greek with CLTK (chapter by chapter)...")
    for label, chapter_text in chapters:
        print(f"  → {label}")
        tokens = analyze_greek(chapter_text)
        for t in tokens:
            t["chapter"] = label
        all_tokens.extend(tokens)

    print("Removing duplicate vocabulary...")
    tokens = deduplicate(all_tokens)
    print(f"  {len(tokens)} unique lemmas")

    print("Building frequency table...")
    freq_table = build_frequency_table(all_tokens)
    top5 = sorted(freq_table.items(), key=lambda x: x[1]["rank"])[:5]
    top5_str = ", ".join(f"{l} ({v['count']}x)" for l, v in top5)
    print(f"  Top 5 lemmas: {top5_str}")

    print("Looking up definitions + Ollama enrichment...")
    entries = enrich(tokens, freq_table)

    print("Post-validating and cleaning entries...")
    entries = post_validate(entries)
    print(f"  {len(entries)} entries after validation")

    print("Writing master CSV...")
    write_csv(entries)
    print(f"  → {OUTPUT_CSV}")

    print("Writing per-chapter CSVs...")
    write_chapter_csvs(entries)

    print("\nAll done!")


if __name__ == "__main__":
    main()
