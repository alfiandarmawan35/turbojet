"""Tes pemotong rekaman (unit 2). Panggilan di sini juga menjadi rekaman rust-anything."""

import io
import json

import pytest

from turbojet.engine import csvio, runner
from turbojet.engine.split.records import split_records


@pytest.mark.parametrize(
    "text, max_records, at_eof, expected",
    [
        ("", 5, True, [0, 0]),
        ("", 5, False, [0, 0]),
        ("a\nb\nc\n", 2, False, [4, 2]),
        ("a\nb\nc\n", 9, False, [6, 3]),
        ("a\r\nb\rc\n", 9, False, [7, 3]),
        ("a\nb", 9, False, [2, 1]),
        ("a\nb", 9, True, [3, 2]),
        ("a\r", 9, False, [0, 0]),  # mungkin \r\n terpotong
        ("a\r", 9, True, [2, 1]),
        ('x,"q\nq"\ny\n', 9, False, [10, 2]),
        ('x,"q\nq', 9, False, [0, 0]),
        ('x,"q\nq', 9, True, [6, 1]),  # kutip tak tertutup di akhir berkas
        ('a""b\n"c""d"\n', 9, False, [12, 2]),
        ("\n\n\n", 2, False, [2, 2]),
        ("é,😀\nñ\n", 1, False, [4, 1]),  # posisi dalam karakter, bukan byte
        ("a\nb\n", 0, True, [0, 0]),
        ("a\nb\n", -1, True, [0, 0]),
    ],
)
def test_split_records(text, max_records, at_eof, expected):
    assert split_records(text, max_records, at_eof) == expected


TEXT = 'kota,total\r\nA,"1\r\n2"\rB,3\n\n"C\n\n",4\r\n"D""",5\nE,"6'


@pytest.mark.parametrize("block", [1, 2, 3, 7, 1000])
@pytest.mark.parametrize("rows", [1, 2, 50])
def test_chunk_reader_tidak_tergantung_ukuran_blok(block, rows):
    reader = csvio.ChunkReader(io.StringIO(TEXT, newline=""), block_chars=block)
    pieces = list(reader.chunks(rows))
    assert "".join(t for t, _ in pieces) == TEXT
    assert sum(n for _, n in pieces) == 7
    assert all(n == rows for _, n in pieces[:-1])


def test_runner_sama_untuk_semua_ukuran_blok(tmp_path):
    inp = tmp_path / "in.csv"
    inp.write_bytes((TEXT + "\n").encode("utf-8"))  # write_text(newline=) baru ada di 3.10
    spec = tmp_path / "job.json"
    spec.write_text(json.dumps({"contract_version": 1, "operation": "group_sum",
                                "options": {"group_by": "kota", "value_column": "total"}}))
    outputs = set()
    for block in (1, 5, 64, 1 << 20):
        out = tmp_path / f"o{block}"
        assert runner.run(str(spec), str(inp), str(out), chunk_rows=2, block_chars=block) == runner.EXIT_OK
        outputs.add(((out / "output.csv").read_bytes(), (out / "errors.csv").read_bytes()))
    assert len(outputs) == 1
