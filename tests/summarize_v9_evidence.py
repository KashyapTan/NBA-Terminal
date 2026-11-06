"""Write compact review evidence; complete HTTP responses stay outside Git.

uv run python tests/summarize_v9_evidence.py --raw /absolute/task/raw --output docs/evidence/v9-chains
"""

import argparse
import hashlib
import json
from pathlib import Path


def summarize(raw, output):
    output.mkdir(parents=True, exist_ok=True)
    files = sorted(raw.glob("*-plan.json"))
    manifest = {"raw_directory": str(raw.resolve()), "files": []}
    rows = [
        "# Controlled real-HTTP verification",
        "",
        "Complete raw responses are outside Git; see raw-artifacts.json for hashes and location.",
        "These are synthetic provider fixtures, not private-league evidence.",
        "",
        "| Host / case | Dated add → drop | Adds / remaining | Forecast evaluations / cap |",
        "|---|---|---|---|",
    ]
    examples = []
    for path in files:
        data = json.loads(path.read_text())
        manifest["files"].append(
            {"name": path.name, "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        )
        plan = data.get("recommended_plan") or {}
        moves = plan.get("moves", [])
        ledger = "; ".join(f"{m['date']} {m['add_id']} → {m['drop_id']}" for m in moves) or "none"
        search = data.get("search", {})
        rows.append(
            f"| {path.stem} | {ledger} | {plan.get('acquisitions', 0)} / {data.get('remaining_adds')} | "
            f"{search.get('evaluations')} / {search.get('evaluation_limit')} |"
        )
        if path.name in {"production-build-2-plan.json", "production-build-harmful-plan.json"}:
            examples.append((path.stem, data))
    for name, data in examples:
        rows.extend(
            [
                "",
                f"## {name}",
                "",
                "Final selected-start Get / Lose / Net vs unchanged roster. "
                "Shooting gross terms are makes/attempts; net is team percentage points.",
                "",
                "| Category | Before | After | Get | Lose | Net |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        impact = data["recommended_plan"]["realized_impact"]
        for key, row in impact["arithmetic"]["categories"].items():
            if key.endswith("pct"):
                get = f"{row['makes']['add']:g}/{row['attempts']['add']:g}"
                lose = f"{row['makes']['drop']:g}/{row['attempts']['drop']:g}"
                net = f"{row['net'] * 100:+.2f} pp"
            else:
                get, lose, net = f"{row['add']:g}", f"{row['drop']:g}", f"{row['net']:+.2f}"
            rows.append(
                f"| {key}{' ↓' if key == 'to' else ''} | {row['before']:.4g} | "
                f"{row['after']:.4g} | {get} | {lose} | {net} |"
            )
        rows.extend(["", "Lost starts: " + "; ".join(f"{r['name']} ({r['date']})" for r in impact["lost_starts"])])
    (output / "verification-summary.md").write_text("\n".join(rows) + "\n")
    (output / "raw-artifacts.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    summarize(args.raw, args.output)
