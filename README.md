# Ancient Greek Vocabulary Pipeline

Turn any Ancient Greek text into a ready-to-study vocabulary list.

Point this tool at a Greek text and it returns a tidy CSV: every meaningful
word, lemmatised, defined, ranked by how often it appears, and sorted so you
can learn the words that matter *before* you sit down to read. It was built by
someone tired of breaking their reading flow every few lines to chase a word
through the lexicon — so it does that chasing in advance, in bulk.

A sample of what comes out, for a single passage:

| lemma | pos | definition | frequency | count | chapter |
|-------|-----|------------|-----------|-------|---------|
| ψυχή | NOUN | soul, life, spirit | core | 42 | Β — 1 |
| αἴσθησις | NOUN | perception, sensation | important | 18 | Β — 5 |
| … | | | | | |

Each row also carries the word's forms as they appear in the text, an example
sentence, and — if you enable it — a best-fit sense chosen by a local language
model. Output is one master CSV plus one CSV per chapter.

---

## What it does

- **Lemmatisation & POS tagging** via [CLTK](https://cltk.org), so inflected
  forms collapse to their dictionary headword.
- **Definitions** pulled from [Wiktionary](https://en.wiktionary.org), falling
  back to a local **Liddell–Scott–Jones** (LSJ) lookup when Wiktionary is silent.
- **Frequency ranking** — every lemma is tagged `core`, `important`,
  `uncommon`, or `rare`, so you can prioritise.
- **Stopword filtering** — common function words (both Classical and Modern
  Greek) are dropped, so the list is words worth learning.
- **Optional LLM enrichment** — a local model (via [Ollama](https://ollama.com))
  picks the most contextually relevant sense and writes a short Classical Greek
  example sentence. Entirely optional; skip it with one flag.
- **Chapter-aware output** — a master `vocab.csv` plus a per-chapter file each.

---

## Installation

Requires Python 3.8+.

```bash
git clone https://github.com/bingzhi-wang/ancient-greek-pipeline.git
cd ancient-greek-pipeline

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

The first run downloads CLTK's Ancient Greek models automatically (a one-time
step). CLTK's Greek pipeline is Stanza-based, which pulls in PyTorch; the
`requirements.txt` is pinned to the **CPU-only** build of PyTorch so you don't
download gigabytes of unused CUDA libraries. If you have an NVIDIA GPU and want
to use it, install the standard `torch` instead.

**Optional — LLM enrichment.** If you want the best-sense/example-sentence
feature, install [Ollama](https://ollama.com) and pull a model:

```bash
ollama pull qwen3:4b
```

Without Ollama, run with `--no-llm` (below) and everything else works.

---

## Usage

The pipeline is driven from the command line — no editing source required.

```bash
python cli.py --input book.txt --output vocab.csv
```

If you don't have Ollama, or just want a faster run:

```bash
python cli.py --input book.txt --output vocab.csv --no-llm
```

See every option:

```bash
python cli.py --help
```

| Flag | Meaning |
|------|---------|
| `--input`, `-i` | Path to the input `.txt` (default `book.txt`) |
| `--output`, `-o` | Path to the master output CSV (default `vocab.csv`) |
| `--no-llm` | Skip the Ollama step; still produces definitions, frequencies, and Wiktionary examples |
| `--ollama-model` | Ollama model to use (default `qwen3:4b`) |

Your input should be a plain-text (UTF-8) Greek file. If it contains
`ΒΙΒΛΙΟΝ` / `ΚΕΦΑΛΑΙΟΝ` headings, the pipeline splits on them for per-chapter
output; otherwise it treats the text as a single unit.

---

## Working from TEI sources (Perseus / First1KGreek)

Most openly available Greek — the whole Hippocratic Corpus, for instance —
comes as TEI XML, not plain text. Two helper scripts bridge the gap.

**1. Download a corpus.** `download_hippocrates.sh` fetches the Greek editions
of the Hippocratic Corpus from
[First1KGreek](https://github.com/OpenGreekAndLatin/First1KGreek) and names each
file by its Latin title:

```bash
bash download_hippocrates.sh          # → sources/hippocrates/*.xml
```

**2. Convert TEI XML to clean text.** `tei_to_txt.py` strips the apparatus,
notes, page breaks, and metadata, keeping only the running Greek. It handles one
file or a whole folder (requires `lxml`: `pip install lxml`):

```bash
python tei_to_txt.py --input sources/hippocrates --output sources/txt
```

**3. Run the pipeline** on any converted file:

```bash
python cli.py --input sources/txt/tlg001_De_prisca_medicina.txt \
              --output vocab_hippocrates_am.csv --no-llm
```

> **A note on dialect.** CLTK's models are trained largely on Attic prose.
> They will lemmatise Ionic (Hippocrates, Herodotus) and other dialects, but
> expect somewhat lower accuracy on dialectal forms. Treat the output as a
> strong first pass, not a critical edition.

---

## How it works

1. **Load & clean** the input text.
2. **Split into chapters** on Greek numeral headings, if present.
3. **CLTK analysis** — tokenise, lemmatise, POS-tag each sentence.
4. **Deduplicate** — one entry per lemma, skipping stopwords and validating
   against LSJ (which also filters out spurious lemmata from noisy input).
5. **Frequency table** — rank every lemma across the whole text.
6. **Define** — Wiktionary first, local LSJ as fallback.
7. **Enrich** (optional) — a local LLM selects the best sense and writes an
   example sentence.
8. **Write CSVs** — master plus one per chapter.

---

## The LSJ dictionary

Definitions fall back to a local SQLite build of the **Liddell–Scott–Jones
Greek–English Lexicon** (`lsj.db`), queried through `lsj_local.py`. If `lsj.db`
is absent the pipeline still runs, but fallback definitions will be empty.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'stanza'` | Install the Stanza extra: `pip install "cltk[stanza]"` (already in `requirements.txt`). |
| `pip` is downloading CUDA / NVIDIA packages | You're getting the GPU build of PyTorch. Install CPU-only first: `pip install torch --index-url https://download.pytorch.org/whl/cpu`, then the rest. |
| Ollama enrichment fails | Start Ollama (`ollama serve`) and pull the model, or just run with `--no-llm`. |
| CLTK model download hangs | Re-run the command; downloads resume. |
| `lxml` not found (TEI converter) | `pip install lxml`. |
| No chapter headings detected | Expected for TEI-derived text; output is treated as a single unit. |

---

## Acknowledgements & licensing

- [CLTK](https://cltk.org) — Ancient Greek NLP
- [Wiktionary](https://en.wiktionary.org) — definitions and examples
- [LSJ](http://www.perseus.tufts.edu/hopper/text?doc=Perseus:text:1999.04.0057) — the lexicon
- [Ollama](https://ollama.com) — local LLM inference
- [First1KGreek](https://github.com/OpenGreekAndLatin/First1KGreek) / Open Greek & Latin — TEI source texts

Source texts from Perseus and First1KGreek are distributed under
**CC BY-SA**; if you redistribute texts or a dataset derived from them, you must
attribute the source and share alike. This repository's own code is released
under the MIT License (see `LICENSE`).
