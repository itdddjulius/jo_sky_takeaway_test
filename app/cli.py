from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI for alert incident service")
    parser.add_argument("command", choices=["submit", "incidents", "metrics"])
    parser.add_argument("--file", help="Path to alerts JSON file")
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    if args.command == "submit":
        if not args.file:
            raise SystemExit("--file is required for submit")
        payload = load_json(args.file)
        resp = httpx.post(f"{args.base_url}/alerts/ingest", json=payload, timeout=30.0)
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))
    elif args.command == "incidents":
        resp = httpx.get(f"{args.base_url}/incidents", timeout=30.0)
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))
    elif args.command == "metrics":
        resp = httpx.get(f"{args.base_url}/metrics/summary", timeout=30.0)
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))


if __name__ == "__main__":
    main()
