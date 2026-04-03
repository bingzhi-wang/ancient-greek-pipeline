# Ancient Greek Vocabulary Pipeline

A pipeline that processes an Ancient Greek text (e.g., Aristotle’s *De Anima* in modern Greek translation) and generates a CSV vocabulary list with:
- Lemmas and word forms
- Part‑of‑speech tags
- Definitions (Wiktionary → LSJ fallback)
- Best sense + example sentence (via Ollama / Qwen3)
- Frequency ranking
- Chapter‑by‑chapter breakdown

---

## Features

- **Text cleaning** – removes footnotes, markup, and chapter markers.
- **Chapter splitting** – handles `ΒΙΒΛΙΟΝ` / `ΚΕΦΑΛΑΙΟΝ` headings.
- **CLTK Ancient Greek NLP** – tokenisation, lemmatisation, POS tagging.
- **Stopword filtering** – common function words (Classical and Modern Greek) are excluded.
- **LSJ dictionary integration** – local SQLite lookup for lemmas not found on Wiktionary.
- **Wiktionary scraping** – fetches definitions and examples for Ancient Greek entries.
- **Ollama enrichment** (optional) – uses local `qwen3:4b` to select the most relevant sense and generate a Classical Greek example sentence.
- **Frequency analysis** – tags words as `core`, `important`, `uncommon`, or `rare`.
- **Output** – one master `vocab.csv` + per‑chapter CSV files.

---

## Requirements

- Python 3.8 or higher
- [Ollama](https://ollama.com/) (optional – for enriched example sentences)  
  Pull the model:  
  ```bash
  ollama pull qwen3:4b

---
## Usage

1. **Prepare your input text**  
   Place your Ancient Greek text (UTF‑8) in a file named `book.txt` in the project root.  
   *The pipeline expects headings like `ΒΙΒΛΙΟΝ Α` or `ΚΕΦΑΛΑΙΟΝ Α´` – adjust if needed.*

2. **Run the pipeline**  
   ```bash
   python pipeline.py
   ```

3. **Outputs**  
   - `vocab.csv` – all unique words with definitions, examples, frequency, etc.  
   - `vocab_<chapter_name>.csv` – one file per chapter.  
   - `ollama_cache.json` – cached Ollama results (safe to delete, regenerated).

---

## Configuration

Edit the top of `pipeline.py` to change:

```python
INPUT_TEXT  = "book.txt"   # Your input file
OUTPUT_CSV  = "vocab.csv"  # Master output file
```

- **Stopwords** – edit the `GRC_STOPWORDS` set.
- **Ollama** – disable by commenting out the call to `ollama_enrich()` in `enrich()`.
- **Wiktionary rate‑limiting** – change `time.sleep(0.5)` if needed.

---

## How It Works

1. **Load & clean** `book.txt` – removes footnotes, `***` blocks, and chapter summaries.
2. **Split into chapters** – using Greek numeral headings.
3. **CLTK analysis** – tokenise, lemmatise, and POS‑tag each sentence.
4. **Deduplicate** – keep one entry per lemma, skip stopwords, validate against LSJ.
5. **Frequency table** – rank lemmas across the whole text.
6. **Definition lookup** – try Wiktionary first, then fall back to local LSJ.
7. **Ollama enrichment** (optional) – ask `qwen3:4b` for the best sense and a Classical Greek example sentence.
8. **Write CSVs** – master + per chapter.

---

## LSJ Dictionary

The pipeline uses a local SQLite version of the **Liddell‑Scott‑Jones Greek‑English Lexicon**.  
- `lsj.db` is required – if missing, the script will still work but fallback definitions will be empty.
- `lsj_local.py` provides the `lsj_lookup(lemma)` function.
- `lsj_combined.xml` is the source file (not used at runtime). Keep it for reference or archival.

---

## Troubleshooting
| Issue                                              | Solution                                                                                       |
| -------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `ModuleNotFoundError: No module named 'lsj_local'` | Ensure `lsj_local.py` is in the same folder as `pipeline.py`.                                  |
| Ollama enrichment fails                            | Start Ollama (`ollama serve`), pull the model (`ollama pull qwen3:4b`), or disable enrichment. |
| CLTK downloads hang                                | Run the one‑line command from Installation again – it resumes.                                 |
| Wiktionary returns no definition                   | The word may be missing from Wiktionary; the pipeline then uses LSJ.                           |
| `book.txt` not found                               | Place your file exactly as `book.txt` in the root, or change `INPUT_TEXT`.                     |

---

## Acknowledgements

- [CLTK](https://cltk.org) – Ancient Greek NLP
- [Wiktionary](https://en.wiktionary.org) – definitions and examples
- [LSJ](http://www.perseus.tufts.edu/hopper/text?doc=Perseus:text:1999.04.0057) – the Greek lexicon
- [Ollama](https://ollama.com) – local LLM inference
