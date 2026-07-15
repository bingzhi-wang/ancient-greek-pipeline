"""
Command-line interface for the Ancient Greek vocabulary pipeline.

Run it like this:

    python cli.py --input book.txt --output vocab.csv

Or, if you don't have Ollama installed (or just want it faster):

    python cli.py --input book.txt --no-llm

Use --help to see all options:

    python cli.py --help
"""

import argparse

from pipeline import main, INPUT_TEXT, OUTPUT_CSV, OLLAMA_MODEL


def build_parser():
    parser = argparse.ArgumentParser(
        prog="ancient-greek-pipeline",
        description=(
            "Build an Ancient Greek vocabulary list from a text file: "
            "lemmatise with CLTK, define via Wiktionary + LSJ, and "
            "(optionally) pick the best sense with a local LLM."
        ),
    )
    parser.add_argument(
        "--input", "-i",
        default=INPUT_TEXT,
        help=f"Path to the input text file (default: {INPUT_TEXT}).",
    )
    parser.add_argument(
        "--output", "-o",
        default=OUTPUT_CSV,
        help=f"Path to the master output CSV (default: {OUTPUT_CSV}).",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help=(
            "Skip the Ollama/LLM enrichment step. Use this if you don't have "
            "Ollama installed, or just want a faster run. You still get "
            "definitions, frequencies, and Wiktionary examples."
        ),
    )
    parser.add_argument(
        "--ollama-model",
        default=OLLAMA_MODEL,
        help=f"Ollama model to use for enrichment (default: {OLLAMA_MODEL}).",
    )
    return parser


def main_cli():
    args = build_parser().parse_args()
    main(
        input_text=args.input,
        output_csv=args.output,
        use_llm=not args.no_llm,
        ollama_model=args.ollama_model,
    )


if __name__ == "__main__":
    main_cli()
