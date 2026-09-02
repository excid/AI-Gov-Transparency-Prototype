"""Command-line entry point for GovSpending data preparation."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx
import pandas as pd

from .data_prep import DataPreparationError, prepare_training_frame, write_training_csv
from .tor_model import fit_preaward_model, save_preaward_artifact


EGP_CONTRACT_URL = "https://opend.data.go.th/govspending/service/egp-contract"


def _fetch_projects(args: argparse.Namespace) -> int:
    api_key = os.getenv("GOVSPENDING_API_KEY")
    if not api_key:
        raise DataPreparationError("Set GOVSPENDING_API_KEY in your shell; never put it in source files.")
    if not 1 <= args.limit <= 1000:
        raise DataPreparationError("limit must be between 1 and 1000")
    params = {
        "api-key": api_key,
        "year": args.year,
        "offset": args.offset,
        "limit": args.limit,
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.get(EGP_CONTRACT_URL, params=params)
        response.raise_for_status()
        payload = response.json()
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
    count = len(payload.get("data", [])) if isinstance(payload, dict) else 0
    print(f"Saved {count} project records to {output}")
    return 0


def _prepare(args: argparse.Namespace) -> int:
    frame = prepare_training_frame(
        project_paths=args.projects,
        bid_paths=args.bids or (),
        cost_paths=args.cost or (),
        label_path=args.labels,
    )
    output = write_training_csv(frame, args.out)
    labelled = int(frame["outcome_label"].notna().sum())
    print(f"Wrote {len(frame)} feature rows to {output}; labelled rows: {labelled}")
    return 0


def _train_tor_model(args: argparse.Namespace) -> int:
    frame = pd.read_csv(args.training_csv, encoding="utf-8-sig")
    artifact = fit_preaward_model(frame, max_rows=args.max_rows, random_state=args.random_state)
    output = save_preaward_artifact(artifact, args.out)
    print(f"Saved {artifact.model_version} with {len(artifact.training_rows)} unsupervised comparison rows to {output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare GovSpending procurement data for anomaly-detection training.")
    commands = parser.add_subparsers(dest="command", required=True)

    fetch = commands.add_parser("fetch-projects", help="Download one EGP-CONTRACT page (up to 1,000 records).")
    fetch.add_argument("--year", type=int, required=True, help="Thai fiscal year, for example 2568")
    fetch.add_argument("--out", required=True, help="Raw JSON output path")
    fetch.add_argument("--offset", type=int, default=0)
    fetch.add_argument("--limit", type=int, default=1000)
    fetch.set_defaults(handler=_fetch_projects)

    prepare = commands.add_parser("prepare", help="Build a training-ready CSV from raw project files.")
    prepare.add_argument("--projects", nargs="+", required=True, help="One or more EGP-CONTRACT JSON, JSONL, or CSV files")
    prepare.add_argument("--bids", action="append", help="Optional EGP-CONTRACT-SUBMIT file; repeat for more files")
    prepare.add_argument("--cost", action="append", help="Optional COST-CONTRACT file; repeat for more files")
    prepare.add_argument("--labels", help="Optional CSV with project_id and outcome_label or label")
    prepare.add_argument("--out", required=True, help="Training CSV output path")
    prepare.set_defaults(handler=_prepare)

    train = commands.add_parser("train-tor-model", help="Fit the pre-award unsupervised TOR comparison artifact.")
    train.add_argument("--training-csv", required=True)
    train.add_argument("--out", default="data/models/tor-isolation-forest.joblib")
    train.add_argument("--max-rows", type=int, default=1000)
    train.add_argument("--random-state", type=int, default=42)
    train.set_defaults(handler=_train_tor_model)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (DataPreparationError, httpx.HTTPError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
