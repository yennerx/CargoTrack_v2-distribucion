import argparse
import json
import sys
from pathlib import Path


def main():
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Compara cobertura de líneas y ramas con mínimos SQA independientes."
    )
    parser.add_argument(
        "report",
        nargs="?",
        type=Path,
        default=project_root / "coverage.json",
        help="Reporte JSON generado por coverage.py.",
    )
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=project_root / "coverage-thresholds.json",
        help="Archivo versionado con los mínimos de líneas y ramas.",
    )
    args = parser.parse_args()

    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        thresholds = json.loads(args.thresholds.read_text(encoding="utf-8"))
        totals = report["totals"]
        line_coverage = float(totals["percent_statements_covered"])
        branch_count = int(totals["num_branches"])
        covered_branches = int(totals["covered_branches"])
        line_minimum = float(thresholds["minimum"]["line_percent"])
        branch_minimum = float(thresholds["minimum"]["branch_percent"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        print(f"No se pudo leer el reporte o los umbrales: {error}")
        return 2

    if branch_count == 0:
        print("El reporte no contiene ramas; no es posible comprobar esta métrica.")
        return 2

    branch_coverage = covered_branches * 100 / branch_count
    print(f"Líneas: {line_coverage:.2f}% (mínimo {line_minimum:.2f}%)")
    print(f"Ramas:  {branch_coverage:.2f}% (mínimo {branch_minimum:.2f}%)")

    failures = []
    if line_coverage < line_minimum:
        failures.append("La cobertura de líneas está por debajo del mínimo SQA.")
    if branch_coverage < branch_minimum:
        failures.append("La cobertura de ramas está por debajo del mínimo SQA.")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1

    print("Cobertura de líneas y ramas aprobada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
