"""Turn GovSpending procurement extracts into training-ready feature rows.

The source API has no confirmed-corruption label. This module therefore prepares
features for anomaly detection by default and can optionally join an externally
curated outcome-label file for future supervised evaluation.
"""

from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd


THAI_MONTHS = {
    "ม.ค.": 1,
    "ก.พ.": 2,
    "มี.ค.": 3,
    "เม.ย.": 4,
    "พ.ค.": 5,
    "มิ.ย.": 6,
    "ก.ค.": 7,
    "ส.ค.": 8,
    "ก.ย.": 9,
    "ต.ค.": 10,
    "พ.ย.": 11,
    "ธ.ค.": 12,
}

IDENTIFIER_COLUMNS = ["project_id", "fiscal_year"]
FEATURE_COLUMNS = [
    "project_money_baht",
    "reference_price_baht",
    "agreed_price_baht",
    "agreed_to_budget_ratio",
    "agreed_to_reference_ratio",
    "discount_from_reference_ratio",
    "contract_count",
    "winner_count",
    "mean_contract_duration_days",
    "has_coordinates",
    "has_geometry",
    "has_contract",
    "bidder_count",
    "bid_price_spread_ratio",
    "lowest_bid_to_agreed_ratio",
    "has_cost_record",
    "cost_installment_count",
    "cost_progress_withdraw_gap",
    "missing_core_field_count",
]
CATEGORY_COLUMNS = [
    "project_type_name",
    "purchase_method_name",
    "dept_name",
    "province",
]
OUTPUT_COLUMNS = IDENTIFIER_COLUMNS + FEATURE_COLUMNS + CATEGORY_COLUMNS + ["outcome_label"]


class DataPreparationError(ValueError):
    """Raised when source data cannot become a trustworthy feature table."""


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _text(value: Any) -> str | None:
    if _is_missing(value):
        return None
    text = str(value).strip()
    return text or None


def _number(value: Any) -> float | None:
    if _is_missing(value):
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9.-]", "", str(value).replace(",", ""))
    if cleaned in {"", ".", "-", "-."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _mean(values: Iterable[float]) -> float | None:
    materialized = list(values)
    return sum(materialized) / len(materialized) if materialized else None


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in {None, 0}:
        return None
    return numerator / denominator


def _as_records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _value(record: Mapping[str, Any], key: str) -> Any:
    if key in record:
        return record[key]
    current: Any = record
    for part in key.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _parse_date(value: Any) -> date | None:
    text = _text(value)
    if text is None or text == "-":
        return None
    try:
        return datetime.fromisoformat(text[:10]).date()
    except ValueError:
        pass
    match = re.fullmatch(r"(\d{1,2})\s+([^\s]+)\s+(\d{2,4})", text)
    if not match or match.group(2) not in THAI_MONTHS:
        return None
    day, month_name, year_text = match.groups()
    thai_year = int(year_text)
    if thai_year < 100:
        thai_year += 2500
    gregorian_year = thai_year - 543 if thai_year > 2400 else thai_year
    try:
        return date(gregorian_year, THAI_MONTHS[month_name], int(day))
    except ValueError:
        return None


def _read_json(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig") as stream:
        payload = json.load(stream)
    if isinstance(payload, Mapping) and "data" in payload:
        payload = payload["data"]
    return _as_records(payload)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise DataPreparationError(f"Invalid JSONL at {path}:{line_number}") from error
            records.extend(_as_records(value.get("data") if isinstance(value, Mapping) and "data" in value else value))
    return records


def _read_csv(path: Path) -> list[dict[str, Any]]:
    for encoding in ("utf-8-sig", "utf-8", "tis-620"):
        try:
            frame = pd.read_csv(path, encoding=encoding)
            return frame.where(pd.notna(frame), None).to_dict(orient="records")
        except UnicodeDecodeError:
            continue
    raise DataPreparationError(f"Cannot decode CSV file: {path}")


def read_records(paths: Sequence[str | Path]) -> list[dict[str, Any]]:
    """Read API JSON/JSONL responses or official bulk CSV downloads."""
    records: list[dict[str, Any]] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_file():
            raise DataPreparationError(f"Input file does not exist: {path}")
        suffix = path.suffix.lower()
        if suffix == ".json":
            records.extend(_read_json(path))
        elif suffix == ".jsonl":
            records.extend(_read_jsonl(path))
        elif suffix == ".csv":
            records.extend(_read_csv(path))
        else:
            raise DataPreparationError(f"Unsupported input type for {path}; use .json, .jsonl, or .csv")
    return records


def _project_row(project: Mapping[str, Any]) -> dict[str, Any] | None:
    project_id = _text(_value(project, "project_id"))
    if project_id is None:
        return None
    budget = _number(_value(project, "project_money"))
    reference_price = _number(_value(project, "price_build"))
    agreed_price = _number(_value(project, "sum_price_agree"))
    contracts = _as_records(_value(project, "contract"))
    durations: list[float] = []
    winner_names: set[str] = set()
    for contract in contracts:
        start = _parse_date(_value(contract, "contract_date"))
        end = _parse_date(_value(contract, "contract_finish_date"))
        if start and end and end >= start:
            durations.append(float((end - start).days))
        winner_name = _text(_value(contract, "winner_name"))
        if winner_name:
            winner_names.add(winner_name)
    lat = _number(_value(project, "project_location.lat"))
    lon = _number(_value(project, "project_location.lon"))
    required = [budget, reference_price, agreed_price, _text(_value(project, "dept_name")), _text(_value(project, "province"))]
    return {
        "project_id": project_id,
        "fiscal_year": _number(_value(project, "year")),
        "project_money_baht": budget,
        "reference_price_baht": reference_price,
        "agreed_price_baht": agreed_price,
        "agreed_to_budget_ratio": _ratio(agreed_price, budget),
        "agreed_to_reference_ratio": _ratio(agreed_price, reference_price),
        "discount_from_reference_ratio": _ratio((reference_price - agreed_price) if reference_price is not None and agreed_price is not None else None, reference_price),
        "contract_count": len(contracts),
        "winner_count": len(winner_names),
        "mean_contract_duration_days": _mean(durations),
        "has_coordinates": int(lat is not None and lon is not None),
        "has_geometry": int(_text(_value(project, "geom")) is not None),
        "has_contract": int(bool(contracts)),
        "project_type_name": _text(_value(project, "project_type_name")),
        "purchase_method_name": _text(_value(project, "purchase_method_name")),
        "dept_name": _text(_value(project, "dept_name")),
        "province": _text(_value(project, "province")),
        "missing_core_field_count": sum(value is None for value in required),
    }


def _bid_summaries(records: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        project_id = _text(_value(record, "project_id"))
        if not project_id:
            continue
        bidders = _as_records(_value(record, "bidder")) or [dict(record)]
        grouped[project_id].extend(bidders)
    summaries: dict[str, dict[str, Any]] = {}
    for project_id, bids in grouped.items():
        prices = [price for price in (_number(_value(bid, "submit_price")) for bid in bids) if price is not None]
        names = {_text(_value(bid, "merchant_name")) for bid in bids}
        names.discard(None)
        lowest = min(prices) if prices else None
        highest = max(prices) if prices else None
        summaries[project_id] = {
            "bidder_count": len(names) or len(bids),
            "bid_price_spread_ratio": _ratio((highest - lowest) if highest is not None and lowest is not None else None, lowest),
            "lowest_bid": lowest,
        }
    return summaries


def _cost_summaries(records: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for record in records:
        project_id = _text(_value(record, "project_id"))
        if not project_id:
            continue
        installments = _as_records(_value(record, "installment"))
        progress_values = [_number(_value(item, "percent_working")) for item in installments]
        withdrawal_values = [_number(_value(item, "percent_withdraw")) for item in installments]
        progress = max((value for value in progress_values if value is not None), default=None)
        withdrawal = max((value for value in withdrawal_values if value is not None), default=None)
        summaries[project_id] = {
            "has_cost_record": 1,
            "cost_installment_count": len(installments),
            "cost_progress_withdraw_gap": (progress - withdrawal) if progress is not None and withdrawal is not None else None,
        }
    return summaries


def _label_map(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or "project_id" not in rows[0]:
        raise DataPreparationError("Label file needs a project_id column")
    label_column = "outcome_label" if "outcome_label" in rows[0] else "label"
    if label_column not in rows[0]:
        raise DataPreparationError("Label file needs outcome_label or label column")
    return {_text(row["project_id"]): row[label_column] for row in rows if _text(row.get("project_id"))}


def prepare_training_frame(
    project_paths: Sequence[str | Path],
    bid_paths: Sequence[str | Path] = (),
    cost_paths: Sequence[str | Path] = (),
    label_path: str | Path | None = None,
) -> pd.DataFrame:
    """Create one feature row per procurement project without exposing winner TINs."""
    return prepare_training_records(
        read_records(project_paths),
        read_records(bid_paths) if bid_paths else (),
        read_records(cost_paths) if cost_paths else (),
        _label_map(label_path),
    )


def prepare_training_records(
    project_records: Iterable[Mapping[str, Any]],
    bid_records: Iterable[Mapping[str, Any]] = (),
    cost_records: Iterable[Mapping[str, Any]] = (),
    labels: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Create one feature row per in-memory procurement project record."""
    project_rows = [row for record in project_records if (row := _project_row(record))]
    if not project_rows:
        raise DataPreparationError("No records with project_id found in project inputs")
    frame = pd.DataFrame(project_rows).drop_duplicates(subset=IDENTIFIER_COLUMNS, keep="last")
    bid_summary = _bid_summaries(bid_records)
    cost_summary = _cost_summaries(cost_records)
    label_values = labels or {}
    for index, row in frame.iterrows():
        project_id = row["project_id"]
        bids = bid_summary.get(project_id, {})
        cost = cost_summary.get(project_id, {})
        agreed_price = _number(row["agreed_price_baht"])
        frame.loc[index, "bidder_count"] = bids.get("bidder_count")
        frame.loc[index, "bid_price_spread_ratio"] = bids.get("bid_price_spread_ratio")
        frame.loc[index, "lowest_bid_to_agreed_ratio"] = _ratio(bids.get("lowest_bid"), agreed_price)
        frame.loc[index, "has_cost_record"] = cost.get("has_cost_record", 0)
        frame.loc[index, "cost_installment_count"] = cost.get("cost_installment_count", 0)
        frame.loc[index, "cost_progress_withdraw_gap"] = cost.get("cost_progress_withdraw_gap")
        frame.loc[index, "outcome_label"] = label_values.get(project_id)
    for column in OUTPUT_COLUMNS:
        if column not in frame:
            frame[column] = None
    return frame[OUTPUT_COLUMNS].sort_values(IDENTIFIER_COLUMNS, kind="stable").reset_index(drop=True)


def write_training_csv(frame: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False, encoding="utf-8-sig")
    return output
