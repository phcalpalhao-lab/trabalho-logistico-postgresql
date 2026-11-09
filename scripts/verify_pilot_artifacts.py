"""Read-only integrity check for exported offline synthetic CSV artifacts."""

from __future__ import annotations

import csv
import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.logistics_generator import (  # noqa: E402
    BASE_IDS,
    FULL_COUNTS,
    InventoryScenarioConfig,
    PILOT_COUNTS,
    SCHEMA,
    SEED,
    _inventory_scenario_metrics,
    validate_dataset,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("pilot", "full"), default="pilot")
    parser.add_argument(
        "--output", type=Path,
        default=PROJECT_ROOT / "generated_data" / "pilot_20261008_1627",
    )
    parser.add_argument(
        "--ascii-output", type=Path,
        default=PROJECT_ROOT / "generated_data" / "pilot_20261008_1627_ascii",
    )
    args = parser.parse_args()

    output = args.output
    ascii_output = args.ascii_output
    expected_counts = FULL_COUNTS if args.profile == "full" else PILOT_COUNTS
    expected_total = sum(expected_counts.values())
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    movement_table = "t_movimentaÇÃo_estoque"
    parsed_data = {table: [] for table in SCHEMA}

    if manifest.get("profile") != args.profile:
        errors.append(f"manifest profile is not {args.profile}")
    if manifest.get("seed") != SEED:
        errors.append(f"unexpected seed: {manifest.get('seed')}")
    if manifest.get("total_new_rows") != expected_total:
        errors.append(f"unexpected total: {manifest.get('total_new_rows')}")
    if manifest.get("database_written") is not False:
        errors.append("manifest does not certify offline-only generation")
    if manifest.get("schema_metadata_status") != "CONFIRMED_A3_NO_DIVERGENCES":
        errors.append("manifest does not record the A3 comparison result")
    if manifest.get("validation_errors") != []:
        errors.append("manifest contains validation errors")
    if "generator_version" in manifest:
        if not manifest.get("dataset_id"):
            errors.append("manifest has no dataset_id")
        generated_at = manifest.get("generated_at_utc")
        try:
            parsed_generated_at = datetime.fromisoformat(
                generated_at.replace("Z", "+00:00")
            )
            if parsed_generated_at.utcoffset() != timedelta(0):
                errors.append("manifest generated_at_utc is not UTC")
        except (AttributeError, TypeError, ValueError):
            errors.append("manifest generated_at_utc is not a valid UTC timestamp")
    inventory_scenario = manifest.get("inventory_scenario", "baseline")
    inventory_config = None
    if inventory_scenario == "operational_diversity":
        raw_config = manifest.get("inventory_config")
        if not isinstance(raw_config, dict):
            errors.append("operational inventory scenario has no configuration")
        else:
            try:
                raw_config["class_weights"] = tuple(
                    tuple(item) for item in raw_config["class_weights"]
                )
                raw_config["healthy_surplus_range"] = tuple(
                    raw_config["healthy_surplus_range"]
                )
                inventory_config = InventoryScenarioConfig(**raw_config)
            except (KeyError, TypeError, ValueError) as error:
                errors.append(f"invalid inventory scenario configuration: {error}")
    elif inventory_scenario != "baseline":
        errors.append(f"unknown inventory scenario: {inventory_scenario}")
    if not all(
        result == "PASS"
        for result in manifest.get("validation_results", {}).values()
    ):
        errors.append("manifest contains a missing or failed validation result")
    if len(manifest.get("csv_sha256", {})) != len(SCHEMA):
        errors.append("manifest does not contain exactly 20 CSV hashes")

    for table, columns in SCHEMA.items():
        path = output / f"{table}.csv"
        if not path.is_file():
            errors.append(f"missing {path.name}")
            continue

        expected_hash = manifest.get("csv_sha256", {}).get(path.name)
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            errors.append(f"SHA-256 mismatch: {path.name}")

        with path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if reader.fieldnames != [column.name for column in columns]:
                errors.append(f"column header mismatch: {path.name}")
            rows = list(reader)
            row_count = len(rows)

        for row_index, raw_row in enumerate(rows):
            parsed_row = {}
            for column in columns:
                raw_value = raw_row[column.name]
                location = f"{path.name}[{row_index}].{column.name}"
                if raw_value == "":
                    if not column.nullable:
                        errors.append(f"{location}: empty value in NOT NULL column")
                    parsed_row[column.name] = None
                    continue
                try:
                    if column.kind == "integer":
                        parsed_row[column.name] = int(raw_value)
                    elif column.kind == "decimal":
                        parsed_row[column.name] = Decimal(raw_value)
                    elif column.kind == "date":
                        parsed_row[column.name] = date.fromisoformat(raw_value)
                    elif column.kind in {"text", "char"}:
                        parsed_row[column.name] = raw_value
                    else:
                        errors.append(f"{location}: unsupported catalog kind {column.kind}")
                except (ValueError, ArithmeticError) as error:
                    errors.append(f"{location}: failed to parse {column.kind}: {error}")
            parsed_data[table].append(parsed_row)

        if row_count != expected_counts[table]:
            errors.append(
                f"{path.name}: expected {expected_counts[table]} rows, got {row_count}"
            )
        if manifest.get("row_counts", {}).get(table) != expected_counts[table]:
            errors.append(f"manifest row count mismatch: {table}")
        planned_range = manifest.get("planned_id_ranges", {}).get(table)
        expected_range = {
            "first": (max([0, *BASE_IDS[table]]) + 1) if expected_counts[table] else None,
            "last": (
                max([0, *BASE_IDS[table]]) + expected_counts[table]
                if expected_counts[table] else None
            ),
            "count": expected_counts[table],
        }
        if (args.profile == "full" or planned_range is not None) and planned_range != expected_range:
            errors.append(f"planned ID range mismatch: {table}")

        ascii_name = (
            "t_movimentacao_estoque.csv"
            if table == movement_table
            else f"{table}.csv"
        )
        ascii_path = ascii_output / ascii_name
        if not ascii_path.is_file():
            errors.append(f"missing ASCII staging copy: {ascii_name}")
            continue
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", ascii_path.name):
            errors.append(f"staging filename is not ASCII-safe: {ascii_path.name}")
        if ascii_path.read_bytes() != path.read_bytes():
            errors.append(f"ASCII staging copy differs from source bytes: {ascii_name}")
        if hashlib.sha256(ascii_path.read_bytes()).hexdigest() != expected_hash:
            errors.append(f"staging SHA-256 mismatch: {ascii_name}")
        with ascii_path.open(encoding="utf-8-sig", newline="") as source:
            staged_reader = csv.DictReader(source)
            if staged_reader.fieldnames != [column.name for column in columns]:
                errors.append(f"staged column header mismatch: {ascii_name}")
            staged_rows = list(staged_reader)
        if staged_rows != rows:
            errors.append(f"staged parsed content differs from source: {ascii_name}")

    csv_count = len(list(output.glob("*.csv")))
    if csv_count != len(SCHEMA):
        errors.append(f"expected {len(SCHEMA)} CSVs, found {csv_count}")
    staging_count = len(list(ascii_output.glob("*.csv")))
    if staging_count != len(SCHEMA):
        errors.append(f"expected {len(SCHEMA)} staged CSVs, found {staging_count}")
    manifest_diagnostics = manifest.get("inventory_diagnostics")
    if manifest_diagnostics is not None and not any(
        "failed to parse" in error or "empty value" in error
        for error in errors
    ):
        expected_diagnostics = _inventory_scenario_metrics(
            parsed_data["t_produto"], parsed_data["t_estoque"]
        )
        if manifest_diagnostics != expected_diagnostics:
            errors.append("manifest inventory diagnostics do not match CSV contents")
        if manifest.get("validation_results", {}).get(
            "inventory_multilocation_diagnostics"
        ) != "PASS":
            errors.append("manifest has no passing multi-warehouse diagnostics result")
    elif manifest.get("generator_version") == "2.1.0":
        errors.append("generator 2.1.0 manifest is missing inventory diagnostics")
    if not any("failed to parse" in error or "empty value" in error for error in errors):
        errors.extend(
            validate_dataset(
                parsed_data,
                expected_counts,
                inventory_config,
            )
        )

    if errors:
        print(f"{args.profile.upper()}_ARTIFACTS_FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        f"{args.profile.upper()}_ARTIFACTS_OK: 20 CSVs, "
        f"{expected_total} rows, 20 SHA-256 hashes."
    )
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
