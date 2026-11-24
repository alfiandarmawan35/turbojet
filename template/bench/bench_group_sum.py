"""Beban nyata untuk ``rust-anything profile`` / ``go``: buat CSV sintetis lalu jalankan runner.

    python bench/bench_group_sum.py [jumlah_baris] [jumlah_grup]
"""

import json
import os
import random
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from turbojet.engine import runner  # noqa: E402


def make_csv(path, rows, groups, seed=7):
    rnd = random.Random(seed)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write("kode,kota,qty,total,catatan\n")
        for i in range(rows):
            g = rnd.randrange(groups)
            whole = rnd.randrange(0, 5_000_000)
            value = f"{whole:,}".replace(",", ".") + f",{rnd.randrange(100):02d}"
            if i % 997 == 0:
                value = "rusak"
            fh.write(f'B{i},KOTA-{g},{rnd.randrange(1, 50)},"{value}",catatan {i % 13}\n')


def main():
    rows = int(sys.argv[1]) if len(sys.argv) > 1 else 200_000
    groups = int(sys.argv[2]) if len(sys.argv) > 2 else 1_000
    # CSV dibuat sekali per (baris, grup) dan dipakai ulang, agar profil hanya mengukur engine.
    cache = os.path.join(tempfile.gettempdir(), "turbojet-bench-data")
    os.makedirs(cache, exist_ok=True)
    inp = os.path.join(cache, f"in-{rows}-{groups}.csv")
    if not os.path.exists(inp):
        make_csv(inp + ".tmp", rows, groups)
        os.replace(inp + ".tmp", inp)
    work = tempfile.mkdtemp(prefix="turbojet-bench-")
    spec = os.path.join(work, "job.json")
    with open(spec, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "contract_version": 1,
                "operation": "group_sum",
                "options": {"group_by": "kota", "value_column": "total", "decimal": "comma"},
                "limits": {"max_groups": max(groups, 1)},
            },
            fh,
        )
    started = time.perf_counter()
    code = runner.run(spec, inp, os.path.join(work, "out"))
    elapsed = time.perf_counter() - started
    with open(os.path.join(work, "out", "result.json"), encoding="utf-8") as fh:
        result = json.load(fh)
    print(json.dumps({"exit": code, "rows": rows, "seconds": round(elapsed, 3), "path": result["engine_path"],
                      "rows_per_sec": int(rows / elapsed), "work": work}))


if __name__ == "__main__":
    main()
