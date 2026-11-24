"""Golden test operasi group_sum. Panggilan di sini juga menjadi rekaman rust-anything
(``record --from-tests -- pytest``), jadi tiap kasus tepi sengaja ditulis eksplisit."""

import json

import pytest

from turbojet.engine.ops.group_sum import aggregate_chunk

COLS = ["kota", "total"]


def opts(**kw):
    base = {"columns": COLS, "group_by": "kota", "value_column": "total", "delimiter": ",", "decimal": "comma"}
    base.update(kw)
    return json.dumps(base)


def run(text, first_row=2, **kw):
    return json.loads(aggregate_chunk(text, opts(**kw), first_row))


def test_desimal_indonesia_dan_urutan_kemunculan():
    out = run('Jakarta,"1.500,50"\nAmbon,200\nJakarta,"2.000"\n')
    assert out == {
        "rows_read": 3,
        "rows_valid": 3,
        "groups": [["Jakarta", 2, "3500.50"], ["Ambon", 1, "200"]],
        "errors": [],
    }


def test_baris_kosong_angka_rusak_dan_jumlah_kolom():
    out = run("Ambon,\nAmbon,12x\n\nAmbon,1.5\nAmbon,7\nTual\n", first_row=10)
    assert out["rows_read"] == 5
    assert out["rows_valid"] == 1
    assert out["groups"] == [["Ambon", 1, "7"]]
    assert out["errors"] == [
        [10, "total", "EMPTY", ""],
        [11, "total", "NOT_A_NUMBER", "12x"],
        [13, "total", "NOT_A_NUMBER", "1.5"],
        [15, "", "BAD_COLUMN_COUNT", "Tual"],
    ]


def test_format_titik_desimal():
    out = run('A,"1,234.5"\nA,-0.25\nA,+3\n', decimal="dot")
    assert out["groups"] == [["A", 3, "1237.25"]]


def test_skala_desimal_terbesar_dipertahankan():
    out = run("A,1\nA,\"2,500\"\nB,\"0,000001\"\n")
    assert out["groups"] == [["A", 2, "3.500"], ["B", 1, "0.000001"]]


def test_di_luar_rentang():
    out = run('A,1234567890123456\nA,"1,1234567"\nA,000000000000000001\n')
    codes = [e[2] for e in out["errors"]]
    assert codes == ["OUT_OF_RANGE", "OUT_OF_RANGE"]
    assert out["groups"] == [["A", 1, "1"]]


def test_kutip_titik_koma_dan_unicode():
    text = 'kota;total\n"Bau-Bau; Sultra";"10,5"\n"Sorong ✓";3\n'.split("\n", 1)[1]
    out = run(text, delimiter=";")
    assert out["groups"] == [["Bau-Bau; Sultra", 1, "10.5"], ["Sorong ✓", 1, "3"]]


def test_digit_non_ascii_ditolak():
    out = run("A,١٢\nA,１\n")
    assert [e[2] for e in out["errors"]] == ["NOT_A_NUMBER", "NOT_A_NUMBER"]


def test_cuplikan_dipotong_40_karakter():
    out = run("A," + "x" * 100 + "\n")
    assert out["errors"][0][3] == "x" * 40


def test_kelompok_kosong_tetap_dihitung():
    out = run(",5\n,6\n")
    assert out["groups"] == [["", 2, "11"]]


def test_batas_kelompok():
    out = run("A,1\nB,2\nC,3\n", max_groups=2)
    assert out == {"error": {"code": "LIMIT_EXCEEDED", "message": "jumlah kelompok melebihi 2"}}


@pytest.mark.parametrize(
    "bad",
    [
        "not json",
        "[]",
        json.dumps({"columns": [], "group_by": "a", "value_column": "a"}),
        json.dumps({"columns": COLS, "group_by": "x", "value_column": "total"}),
        json.dumps({"columns": COLS, "group_by": "kota", "value_column": "total", "delimiter": ":"}),
        json.dumps({"columns": COLS, "group_by": "kota", "value_column": "total", "decimal": "x"}),
        json.dumps({"columns": COLS, "group_by": "kota", "value_column": "total", "max_groups": 0}),
    ],
)
def test_opsi_tidak_valid(bad):
    out = json.loads(aggregate_chunk("A,1\n", bad, 2))
    assert out["error"]["code"] == "INVALID_OPTIONS"


def test_sel_melebihi_batas_csv():
    out = json.loads(aggregate_chunk("A," + "9" * 131073 + "\n", opts(), 2))
    assert out == {"error": {"code": "CSV_ERROR", "message": "field larger than field limit (131072)"}}


def test_potongan_kosong():
    assert run("") == {"rows_read": 0, "rows_valid": 0, "groups": [], "errors": []}
