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