//! The Rust port of `turbojet/engine/split/`.
//!
//! Scans bytes: `"`, `\r` and `\n` are ASCII and never occur inside a multibyte UTF-8 sequence.
//! Positions are returned in characters (Python `str` indices): every byte that is not a UTF-8
//! continuation byte (`0b10xx_xxxx`) starts one character.

#![forbid(unsafe_code)]

/// Port of `split_records` (`turbojet/engine/split/records.py:17`).
pub fn split_records(text: String, max_records: i64, at_eof: bool) -> Result<Vec<i64>, String> {
    let (pos, count) = scan(text.as_bytes(), max_records, at_eof);
    Ok(vec![pos, count])
}

fn scan(bytes: &[u8], max_records: i64, at_eof: bool) -> (i64, i64) {
    if max_records <= 0 {
        return (0, 0);
    }
    let len = bytes.len();
    let total_chars = char_len(bytes);
    let (mut pos, mut count, mut chars) = (0_i64, 0_i64, 0_i64);
    let mut in_quote = false;
    let mut i = 0;
    while i < len {
        let b = bytes[i];
        if b & 0xC0 != 0x80 {
            chars += 1;
        }
        i += 1;
        match b {
            b'"' => in_quote = !in_quote,
            b'\n' | b'\r' => {
                let crlf = b == b'\r' && bytes.get(i) == Some(&b'\n');
                if crlf {
                    chars += 1;
                    i += 1;
                }
                let lone_cr_at_end = b == b'\r' && !crlf && i == len;
                if lone_cr_at_end && !at_eof {
                    return (pos, count);
                }
                if !in_quote {
                    count += 1;
                    pos = chars;
                    if count == max_records {
                        return (pos, count);
                    }
                }
            }
            _ => {}
        }
    }
    // An unterminated last line (or an unclosed quote) is incomplete unless the file ended.
    if at_eof && pos < total_chars {
        return (total_chars, count + 1);
    }
    (pos, count)
}

fn char_len(bytes: &[u8]) -> i64 {
    let n = bytes.iter().filter(|b| **b & 0xC0 != 0x80).count();
    i64::try_from(n).unwrap_or(i64::MAX)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn split(text: &str, max: i64, eof: bool) -> (i64, i64) {
        scan(text.as_bytes(), max, eof)
    }

    #[test]
    fn lines_and_endings() {
        assert_eq!(split("a\r\nb\rc\n", 9, false), (7, 3));
        assert_eq!(split("a\nb", 9, false), (2, 1));
        assert_eq!(split("a\nb", 9, true), (3, 2));
        assert_eq!(split("a\r", 9, false), (0, 0));
        assert_eq!(split("a\r", 9, true), (2, 1));
    }

    #[test]
    fn quotes_and_chars() {
        assert_eq!(split("x,\"q\nq\"\ny\n", 9, false), (10, 2));
        assert_eq!(split("x,\"q\nq", 9, true), (6, 1));
        assert_eq!(split("é,😀\nñ\n", 1, false), (4, 1));
    }
}
