"""Uji ujung ke ujung runner: kontrak berkas, encoding, potongan, kode keluar."""

import csv
import json
import os

import pytest

from turbojet.engine import contract, registry, runner


def write(path, data, encoding="utf-8"):
    with open(path, "w", encoding=encoding, newline="") as fh:
        fh.write(data)
    return str(path)


def spec(tmp_path, **limits):
    s = {
        "contract_version": 1,
        "operation": "group_sum",
        "options": {"group_by": "kota", "value_column": "total", "decimal": "comma"},
        "limits": limits,
    }
    return write(tmp_path / "job.json", json.dumps(s))


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.reader(fh))


SAMPLE = 'kota;total\nJakarta;"1.000,25"\n"Ambon\nKota";5\nJakarta;x\n\nAmbon\nKota;1\n'


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
def test_run_lengkap_dengan_manifest(tmp_path, encoding):
    inp = write(tmp_path / "in.csv", SAMPLE, encoding)
    out = tmp_path / "out"
    assert runner.run(spec(tmp_path), inp, str(out)) == runner.EXIT_OK
    assert read_csv(out / "output.csv") == [
        ["kota", "rows", "sum_total"],
        ["Jakarta", "1", "1000.25"],
        ["Ambon\nKota", "1", "5"],
        ["Kota", "1", "1"],
    ]
    # Baris 6-7 "Ambon\nKota;1" tanpa kutip = dua rekaman: kolom kurang lalu kelompok baru.
    errors = read_csv(out / "errors.csv")
    assert errors[0] == ["row", "column", "code", "value"]
    assert [r[2] for r in errors[1:]] == ["NOT_A_NUMBER", "BAD_COLUMN_COUNT"]
    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    assert result["delimiter"] == ";"
    assert result["engine_path"] == registry.describe()["group_sum"]["path"]
    assert (result["rows_read"], result["rows_valid"], result["rows_rejected"]) == (5, 3, 2)
    # Nomor rekaman spreadsheet: sel berkutip berisi baris baru tetap satu baris.
    assert [r[0] for r in errors[1:]] == ["4", "6"]
    manifest = contract.verify_manifest(str(out))
    assert manifest and manifest["engine_path"] == result["engine_path"]


def test_hasil_sama_untuk_semua_ukuran_potongan(tmp_path):
    rows = ["kota,total"] + [f'K{i % 7},"{i}.{i % 1000:03d},5"' if i % 11 else f"K{i % 7},rusak" for i in range(1, 400)]
    inp = write(tmp_path / "in.csv", "\n".join(rows) + "\n")
    s = spec(tmp_path)
    outputs = []
    for chunk in (1, 3, 50, 1000):
        out = tmp_path / f"out{chunk}"
        assert runner.run(s, inp, str(out), chunk_rows=chunk) == runner.EXIT_OK
        outputs.append(((out / "output.csv").read_bytes(), (out / "errors.csv").read_bytes()))
    assert all(o == outputs[0] for o in outputs)


def test_cp1252(tmp_path):
    inp = tmp_path / "in.csv"
    inp.write_bytes("kota,total\nCaf\xe9,1\n".encode("latin-1"))
    out = tmp_path / "out"
    assert runner.run(spec(tmp_path), str(inp), str(out)) == runner.EXIT_OK
    assert read_csv(out / "output.csv")[1] == ["Café", "1", "1"]


def test_kode_keluar_input_dan_batas(tmp_path):
    inp = write(tmp_path / "in.csv", "kota,total\nA,1\nB,2\nC,3\n")
    assert runner.run(spec(tmp_path, max_groups=2), inp, str(tmp_path / "o1")) == runner.EXIT_LIMIT
    assert json.loads((tmp_path / "o1" / "failure.json").read_text())["code"] == "LIMIT_EXCEEDED"
    assert not (tmp_path / "o1" / "manifest.json").exists()

    assert runner.run(spec(tmp_path, max_rows=2), inp, str(tmp_path / "o2")) == runner.EXIT_LIMIT

    empty = write(tmp_path / "empty.csv", "")
    assert runner.run(spec(tmp_path), empty, str(tmp_path / "o3")) == runner.EXIT_INPUT

    wrong_col = write(tmp_path / "w.csv", "a,b\n1,2\n")
    assert runner.run(spec(tmp_path), wrong_col, str(tmp_path / "o4")) == runner.EXIT_INPUT

    bad_spec = write(tmp_path / "bad.json", json.dumps({"contract_version": 9, "operation": "group_sum"}))
    assert runner.run(bad_spec, inp, str(tmp_path / "o5")) == runner.EXIT_INPUT


def test_direktori_keluaran_harus_baru(tmp_path):
    inp = write(tmp_path / "in.csv", "kota,total\nA,1\n")
    os.makedirs(tmp_path / "exists")
    assert runner.run(spec(tmp_path), inp, str(tmp_path / "exists")) == runner.EXIT_INTERNAL


def test_manifest_menolak_berkas_yang_diubah(tmp_path):
    inp = write(tmp_path / "in.csv", "kota,total\nA,1\n")
    out = tmp_path / "out"
    runner.run(spec(tmp_path), inp, str(out))
    (out / "output.csv").write_text("diubah")
    assert contract.verify_manifest(str(out)) is None
