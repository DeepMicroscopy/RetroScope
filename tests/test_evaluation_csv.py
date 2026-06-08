"""Evaluation: CSV result accumulation + summary."""

from __future__ import annotations

import csv

from retroscope.evaluation.csv_io import ResultWriter, mean_std


def test_mean_std():
    mean, std, n = mean_std([2.0, 4.0, 6.0])
    assert (mean, n) == (4.0, 3)
    assert abs(std - 2.0) < 1e-9
    assert mean_std([]) == (0.0, 0.0, 0)
    assert mean_std([5.0]) == (5.0, 0.0, 1)


def test_result_writer_raw_and_summary(tmp_path):
    rw = ResultWriter("demo")
    for axis in ("X", "Y"):
        for rep, v in enumerate((10.0, 12.0, 14.0)):
            rw.add(axis=axis, rep=rep, value=v)
    rw.summarize(["axis"], ["value"])

    # two groups x (mean, std, n) = 6 summary rows + 6 trial rows
    trials = [r for r in rw.rows if r["row_type"] == "trial"]
    means = [r for r in rw.rows if r["row_type"] == "summary_mean"]
    assert len(trials) == 6
    assert len(means) == 2
    x_mean = next(r for r in means if r["axis"] == "X")["value"]
    assert x_mean == 12.0

    path = rw.save(tmp_path)
    assert path.exists()
    with path.open() as f:
        rows = list(csv.DictReader(f))
    assert any(r["row_type"] == "summary_std" for r in rows)
    assert {"axis", "value", "row_type"} <= set(rows[0].keys())
