"""Evaluation: CSV result accumulation for the evaluation.

Note: Partially AI-generated.
"""

from __future__ import annotations

import csv
import math
from datetime import datetime
from pathlib import Path


def mean_std(values: list[float]) -> tuple[float, float, int]:
    nums = [float(v) for v in values if v is not None]
    n = len(nums)
    if n == 0:
        return (0.0, 0.0, 0)
    mean = sum(nums) / n
    if n < 2:
        return (mean, 0.0, n)
    var = sum((x - mean) ** 2 for x in nums) / (n - 1)
    return (mean, math.sqrt(var), n)


class ResultWriter:
    """Accumulates trial rows and computes grouped summary rows."""

    def __init__(self, experiment: str) -> None:
        self.experiment = experiment
        self._rows: list[dict] = []

    def add(self, **fields) -> None:
        row = {"row_type": "trial"}
        row.update(fields)
        self._rows.append(row)

    def summarize(self, group_keys: list[str], value_keys: list[str]) -> None:
        """Append mean/std/n rows for each group of trial rows."""
        groups: dict[tuple, list[dict]] = {}
        for r in self._rows:
            if r.get("row_type") != "trial":
                continue
            key = tuple(r.get(k) for k in group_keys)
            groups.setdefault(key, []).append(r)
        for key, members in groups.items():
            base = {k: v for k, v in zip(group_keys, key)}
            for stat in ("mean", "std", "n"):
                row = {"row_type": f"summary_{stat}"}
                row.update(base)
                for vk in value_keys:
                    vals = [m[vk] for m in members if m.get(vk) is not None]
                    mean, std, n = mean_std(vals)
                    row[vk] = {"mean": mean, "std": std, "n": n}[stat]
                self._rows.append(row)

    def save(self, out_dir: Path) -> Path:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"{self.experiment}_{stamp}.csv"
        fieldnames: list[str] = []
        for r in self._rows:
            for k in r:
                if k not in fieldnames:
                    fieldnames.append(k)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in self._rows:
                writer.writerow(r)
        return path

    @property
    def rows(self) -> list[dict]:
        return self._rows
