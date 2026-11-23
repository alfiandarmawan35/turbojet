"""Baca CSV secara bertahap: deteksi encoding dan potong per rekaman (sadar tanda kutip)."""

from turbojet.engine.split import records

UTF8_BOM = b"\xef\xbb\xbf"
SAMPLE_BYTES = 64 * 1024


def detect_encoding(path):
    with open(path, "rb") as fh:
        sample = fh.read(SAMPLE_BYTES)
    if sample.startswith(UTF8_BOM):
        return "utf-8-sig"
    try:
        sample.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError as exc:
        # Karakter multibyte terpotong di ujung sampel bukan tanda bukan-UTF-8.
        if exc.start >= len(sample) - 3 and len(sample) == SAMPLE_BYTES:
            return "utf-8"
        return "cp1252"


BLOCK_CHARS = 4 * 1024 * 1024


class ChunkReader:
    """Baca berkas teks per blok dan keluarkan potongan berisi rekaman CSV utuh.

    Pencarian batas rekaman ada di ``split.records.split_records`` (fungsi murni, diport ke Rust).
    Berkas harus dibuka dengan ``newline=""`` agar akhir baris tidak diterjemahkan.
    """

    def __init__(self, text_file, block_chars=BLOCK_CHARS):
        self.fh = text_file
        self.block_chars = block_chars
        self.buf = ""
        self.eof = False

    def take(self, max_records):
        """``(teks, n)`` dengan 1..max_records rekaman utuh, atau ``("", 0)`` bila berkas habis."""
        while True:
            consumed, count = records.split_records(self.buf, max_records, self.eof)
            if count and (count == max_records or self.eof):
                text = self.buf[:consumed]
                self.buf = self.buf[consumed:]
                return text, count
            if self.eof:
                return "", 0
            data = self.fh.read(self.block_chars)
            if data:
                self.buf += data
            else:
                self.eof = True

    def chunks(self, chunk_rows):
        while True:
            text, count = self.take(chunk_rows)
            if not count:
                return
            yield text, count
