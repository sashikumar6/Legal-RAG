#!/usr/bin/env python3
"""Run the federal corpus ingestion pipeline from local XML files."""

import argparse
import logging
import sys
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.ingestion.pipeline import run_ingestion


def main():
    parser = argparse.ArgumentParser(
        description="Ingest federal U.S. Code XML files into the system."
    )
    parser.add_argument(
        "--base-path",
        type=str,
        default=None,
        help="Base path to XML files (default: FEDERAL_XML_BASE_PATH env var or ./)",
    )
    parser.add_argument(
        "--title",
        type=int,
        default=None,
        help="Ingest only a specific title number (e.g., 8, 18, 42)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    if args.title:
        from app.core.config import TITLE_FILE_MAP
        from app.ingestion import parse_uslm_title

        base = Path(args.base_path) if args.base_path else Path(".")
        filename = TITLE_FILE_MAP.get(args.title)
        if not filename:
            print(f"Error: No file mapping for Title {args.title}")
            sys.exit(1)

        xml_path = base / filename
        if not xml_path.exists():
            print(f"Error: File not found: {xml_path}")
            sys.exit(1)

        chunks = parse_uslm_title(xml_path, args.title)
        print(f"Title {args.title}: {len(chunks)} chunks parsed")
        if chunks:
            print(f"  First chunk: {chunks[0].canonical_citation or 'N/A'}")
            print(f"  Last chunk: {chunks[-1].canonical_citation or 'N/A'}")
    else:
        results = run_ingestion(args.base_path)
        print("\nIngestion Summary:")
        for title, count in sorted(results.items()):
            print(f"  Title {title}: {count} chunks")
        print(f"  Total: {sum(results.values())} chunks")


if __name__ == "__main__":
    main()
