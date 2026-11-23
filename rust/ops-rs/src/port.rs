//! The Rust port of `turbojet/engine/ops/`.
//!
//! Parity rules with the Python reference:
//! * CSV follows CPython's `_csv.c` reader state machine (default dialect, `"` quote,
//!   double-quote escaping, non-strict), fed line by line as `io.StringIO(newline="")` splits.
//! * Numbers: ASCII digits only, exact decimal sums at scale <= 6, Python `Decimal` formatting.
//! * JSON output matches `json.dumps(ensure_ascii=False, separators=(",", ":"))`.

#![forbid(unsafe_code)]

use std::collections::HashMap;

use serde_json::{Map, Value, json};

const MAX_INT_DIGITS: usize = 15;
const MAX_FRAC_DIGITS: usize = 6;
const SNIPPET_CHARS: usize = 40;
const DELIMITERS: [char; 4] = [',', ';', '\t', '|'];
const FIELD_LIMIT: usize = 131_072;
const SCALE: u32 = 6;

// ------------------------------------------------------------------ CSV (CPython `_csv.c`)

#[derive(Clone, Copy, PartialEq)]
enum State {
    StartRecord,
    StartField,
    InField,
    InQuotedField,
    QuoteInQuotedField,
    EatCrnl,
}

/// One input character, or the end-of-line marker the reader feeds after every line.
#[derive(Clone, Copy)]
enum Ch {
    C(char),
    Eol,
}

struct Reader {
    delim: char,
    state: State,
    field: String,
    field_len: usize,
    fields: Vec<String>,
}

impl Reader {
    fn new(delim: char) -> Self {
        Reader {
            delim,
            state: State::StartRecord,
            field: String::new(),
            field_len: 0,
            fields: Vec::new(),
        }
    }

    fn save_field(&mut self) {
        self.fields.push(std::mem::take(&mut self.field));
        self.field_len = 0;
    }

    fn add_char(&mut self, c: char) -> Result<(), String> {
        if self.field_len >= FIELD_LIMIT {
            return Err(format!("field larger than field limit ({FIELD_LIMIT})"));
        }
        self.field.push(c);
        self.field_len += 1;
        Ok(())
    }

    fn process(&mut self, ch: Ch) -> Result<(), String> {
        let (c, eol) = match ch {
            Ch::C(c) => (c, false),
            Ch::Eol => ('\0', true),
        };
        let newline = !eol && (c == '\n' || c == '\r');
        match self.state {
            State::StartRecord => {
                if eol {
                    return Ok(());
                }
                if newline {
                    self.state = State::EatCrnl;
                    return Ok(());
                }
                self.state = State::StartField;
                self.start_field(c, eol, newline)
            }
            State::StartField => self.start_field(c, eol, newline),
            State::InField => {
                if newline || eol {
                    self.save_field();
                    self.state = if eol {
                        State::StartRecord
                    } else {
                        State::EatCrnl
                    };
                } else if c == self.delim {
                    self.save_field();
                    self.state = State::StartField;
                } else {
                    self.add_char(c)?;
                }
                Ok(())
            }
            State::InQuotedField => {
                if eol {
                } else if c == '"' {
                    self.state = State::QuoteInQuotedField;
                } else {
                    self.add_char(c)?;
                }
                Ok(())
            }
            State::QuoteInQuotedField => {
                if !eol && c == '"' {
                    self.add_char(c)?;
                    self.state = State::InQuotedField;
                } else if !eol && c == self.delim {
                    self.save_field();
                    self.state = State::StartField;
                } else if newline || eol {
                    self.save_field();
                    self.state = if eol {
                        State::StartRecord
                    } else {
                        State::EatCrnl
                    };
                } else {
                    self.add_char(c)?;
                    self.state = State::InField;
                }
                Ok(())
            }
            State::EatCrnl => {
                if newline {
                } else if eol {
                    self.state = State::StartRecord;
                } else {
                    return Err(
                        "new-line character seen in unquoted field - do you need to open \
                                the file with newline=''?"
                            .to_string(),
                    );
                }
                Ok(())
            }
        }
    }

    fn start_field(&mut self, c: char, eol: bool, newline: bool) -> Result<(), String> {
        if newline || eol {
            self.save_field();
            self.state = if eol {
                State::StartRecord
            } else {
                State::EatCrnl
            };
        } else if c == '"' {
            self.state = State::InQuotedField;
        } else if c == self.delim {
            self.save_field();
        } else {
            self.add_char(c)?;
            self.state = State::InField;
        }
        Ok(())
    }
}

/// Lines as `io.StringIO(text, newline="")` yields them: split after `\n`, `\r` or `\r\n`.
fn lines(text: &str) -> Vec<&str> {
    let bytes = text.as_bytes();
    let mut out = Vec::new();
    let mut start = 0;
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'\n' => {
                out.push(&text[start..=i]);
                start = i + 1;
            }
            b'\r' => {
                let end = if bytes.get(i + 1) == Some(&b'\n') {
                    i + 1
                } else {
                    i
                };
                out.push(&text[start..=end]);
                start = end + 1;
                i = end;
            }
            _ => {}
        }
        i += 1;
    }
    if start < bytes.len() {
        out.push(&text[start..]);
    }
    out
}

/// Every record `csv.reader` returns for `text`, empty records (`[]`) included, and the
/// reader error that stopped it, if any (records before the error are still returned).
fn read_records(text: &str, delim: char) -> (Vec<Vec<String>>, Option<String>) {
    let mut reader = Reader::new(delim);
    let mut records = Vec::new();
    let mut pending = false;
    for line in lines(text) {
        if !pending {
            reader.fields = Vec::new();
            reader.field.clear();
            reader.field_len = 0;
            reader.state = State::StartRecord;
        }
        let mut fed = line.chars().map(Ch::C).chain(std::iter::once(Ch::Eol));
        if let Err(e) = fed.try_for_each(|c| reader.process(c)) {
            return (records, Some(e));
        }
        pending = reader.state != State::StartRecord;
        if !pending {
            records.push(std::mem::take(&mut reader.fields));
        }
    }
    if pending && (reader.field_len != 0 || reader.state == State::InQuotedField) {
        reader.save_field();
        records.push(std::mem::take(&mut reader.fields));
    }
    (records, None)
}

// ------------------------------------------------------------------ options

struct Options {
    columns: Vec<String>,
    group_by: String,
    value_column: String,
    delimiter: char,
    comma: bool,
    max_groups: u64,
}

fn invalid(msg: &str) -> String {
    msg.to_string()
}

/// `{"error": {"code", "message"}}`, as `_error_json` writes it.
fn error_json(code: &str, message: &str) -> String {
    let mut err = Map::new();
    err.insert("code".into(), code.into());
    err.insert("message".into(), message.into());
    let mut out = Map::new();
    out.insert("error".into(), Value::Object(err));
    Value::Object(out).to_string()
}

fn as_str_in<'a>(v: Option<&'a Value>, allowed: &[&str]) -> Option<&'a str> {
    match v {
        Some(Value::String(s)) if allowed.contains(&s.as_str()) => Some(s.as_str()),
        _ => None,
    }
}

fn parse_options(options_json: &str) -> Result<Options, String> {
    let value: Value =
        serde_json::from_str(options_json).map_err(|_| invalid("opsi bukan JSON"))?;
    let Value::Object(opts) = value else {
        return Err(invalid("opsi harus objek JSON"));
    };
    let columns: Vec<String> = match opts.get("columns") {
        Some(Value::Array(items)) if !items.is_empty() => items
            .iter()
            .map(|c| c.as_str().map(str::to_string))
            .collect::<Option<Vec<_>>>()
            .ok_or_else(|| invalid("columns harus daftar nama kolom"))?,
        _ => return Err(invalid("columns harus daftar nama kolom")),
    };
    let cols: Vec<&str> = columns.iter().map(String::as_str).collect();
    let group_by = as_str_in(opts.get("group_by"), &cols)
        .ok_or_else(|| invalid("group_by tidak ada di columns"))?;
    let value_column = as_str_in(opts.get("value_column"), &cols)
        .ok_or_else(|| invalid("value_column tidak ada di columns"))?;
    let delimiter = match opts.get("delimiter") {
        None => ",",
        v => as_str_in(v, &[",", ";", "\t", "|"])
            .ok_or_else(|| invalid("delimiter tidak didukung"))?,
    };
    let decimal = match opts.get("decimal") {
        None => "comma",
        v => as_str_in(v, &["comma", "dot"])
            .ok_or_else(|| invalid("decimal harus comma atau dot"))?,
    };
    let max_groups = match opts.get("max_groups") {
        None => 100_000,
        Some(Value::Number(n)) => match (n.as_i64(), n.as_u64()) {
            (Some(i), _) if i >= 1 => i.unsigned_abs(),
            (None, Some(u)) => u,
            _ => return Err(invalid("max_groups harus bilangan bulat positif")),
        },
        Some(_) => return Err(invalid("max_groups harus bilangan bulat positif")),
    };
    Ok(Options {
        group_by: group_by.to_string(),
        value_column: value_column.to_string(),
        delimiter: delimiter.chars().next().unwrap_or(','),
        comma: decimal == "comma",
        max_groups,
        columns,
    })
}

// ------------------------------------------------------------------ numbers

/// An exact decimal: `mant / 10^6`, written with `scale` fraction digits, plus Python's `-0`.
#[derive(Clone, Copy)]
struct Dec {
    mant: i128,
    scale: u32,
    neg_zero: bool,
}

impl Dec {
    fn add(self, other: Dec) -> Dec {
        let mant = self.mant + other.mant;
        let neg_zero = self.mant == 0 && other.mant == 0 && self.neg_zero && other.neg_zero;
        Dec {
            mant,
            scale: self.scale.max(other.scale),
            neg_zero,
        }
    }

    fn format(self) -> String {
        let unit = 10_i128.pow(SCALE - self.scale);
        let v = (self.mant / unit).unsigned_abs();
        let sign = if self.mant < 0 || self.neg_zero {
            "-"
        } else {
            ""
        };
        if self.scale == 0 {
            return format!("{sign}{v}");
        }
        let p = 10_u128.pow(self.scale);
        format!(
            "{sign}{}.{:0width$}",
            v / p,
            v % p,
            width = self.scale as usize
        )
    }
}

fn all_digits(s: &str) -> bool {
    !s.is_empty() && s.bytes().all(|b| b.is_ascii_digit())
}

/// `D{1,3}(SEP D{3})+ | D+`
fn int_part_ok(s: &str, sep: char) -> bool {
    if all_digits(s) {
        return true;
    }
    let groups: Vec<&str> = s.split(sep).collect();
    groups.len() >= 2
        && all_digits(groups[0])
        && groups[0].len() <= 3
        && groups[1..].iter().all(|g| g.len() == 3 && all_digits(g))
}

fn parse_number(raw: &str, comma: bool) -> Result<Dec, &'static str> {
    let text = raw.trim_matches([' ', '\t']);
    if text.is_empty() {
        return Err("EMPTY");
    }
    let (thousands, decimal) = if comma { ('.', ',') } else { (',', '.') };
    let (negative, body) = match text.as_bytes()[0] {
        b'-' => (true, &text[1..]),
        b'+' => (false, &text[1..]),
        _ => (false, text),
    };
    let (int_raw, frac) = match body.split_once(decimal) {
        Some((i, f)) => (i, Some(f)),
        None => (body, None),
    };
    if !int_part_ok(int_raw, thousands) || frac.is_some_and(|f| !all_digits(f)) {
        return Err("NOT_A_NUMBER");
    }
    let int_digits: String = int_raw.chars().filter(|c| *c != thousands).collect();
    let frac = frac.unwrap_or("");
    if int_digits.trim_start_matches('0').len() > MAX_INT_DIGITS || frac.len() > MAX_FRAC_DIGITS {
        return Err("OUT_OF_RANGE");
    }
    let mut mant: i128 = 0;
    for b in int_digits.bytes().chain(frac.bytes()) {
        mant = mant * 10 + i128::from(b - b'0');
    }
    let scale = u32::try_from(frac.len()).unwrap_or(SCALE);
    mant *= 10_i128.pow(SCALE - scale);
    let neg_zero = negative && mant == 0;
    Ok(Dec {
        mant: if negative { -mant } else { mant },
        scale,
        neg_zero,
    })
}

fn snippet(text: &str) -> String {
    text.chars().take(SNIPPET_CHARS).collect()
}

// ------------------------------------------------------------------ operations

/// Port of `aggregate_chunk` (`turbojet/engine/ops/group_sum.py:45`).
pub fn aggregate_chunk(
    chunk_text: String,
    options_json: String,
    first_row: i64,
) -> Result<String, String> {
    let opts = match parse_options(&options_json) {
        Ok(o) => o,
        Err(m) => return Ok(error_json("INVALID_OPTIONS", &m)),
    };
    let group_idx = opts
        .columns
        .iter()
        .position(|c| *c == opts.group_by)
        .unwrap_or(0);
    let value_idx = opts
        .columns
        .iter()
        .position(|c| *c == opts.value_column)
        .unwrap_or(0);
    let delim = opts.delimiter.to_string();

    let mut order: Vec<String> = Vec::new();
    let mut groups: HashMap<String, (u64, Dec)> = HashMap::new();
    let mut errors: Vec<Value> = Vec::new();
    let (mut rows_read, mut rows_valid) = (0_u64, 0_u64);

    let (records, csv_error) = read_records(&chunk_text, opts.delimiter);
    for (offset, record) in records.into_iter().enumerate() {
        if record.is_empty() {
            continue;
        }
        let row_no = i128::from(first_row) + i128::try_from(offset).unwrap_or(i128::MAX);
        rows_read += 1;
        if record.len() != opts.columns.len() {
            errors.push(json!([
                row_no,
                "",
                "BAD_COLUMN_COUNT",
                snippet(&record.join(&delim))
            ]));
            continue;
        }
        let raw = &record[value_idx];
        let value = match parse_number(raw, opts.comma) {
            Ok(v) => v,
            Err(code) => {
                errors.push(json!([row_no, opts.value_column, code, snippet(raw)]));
                continue;
            }
        };
        let key = &record[group_idx];
        if let Some(entry) = groups.get_mut(key) {
            entry.0 += 1;
            entry.1 = entry.1.add(value);
        } else {
            if order.len() as u64 >= opts.max_groups {
                let msg = format!("jumlah kelompok melebihi {}", opts.max_groups);
                return Ok(error_json("LIMIT_EXCEEDED", &msg));
            }
            order.push(key.clone());
            groups.insert(key.clone(), (1, value));
        }
        rows_valid += 1;
    }
    if let Some(e) = csv_error {
        return Ok(error_json("CSV_ERROR", &e));
    }

    let group_rows: Vec<Value> = order
        .iter()
        .map(|k| {
            let (count, total) = groups[k];
            json!([k, count, total.format()])
        })
        .collect();
    let mut out = Map::new();
    out.insert("rows_read".into(), rows_read.into());
    out.insert("rows_valid".into(), rows_valid.into());
    out.insert("groups".into(), Value::Array(group_rows));
    out.insert("errors".into(), Value::Array(errors));
    serde_json::to_string(&out).map_err(|e| format!("RuntimeError: {e}"))
}

/// Port of `detect_delimiter` (`turbojet/engine/ops/preview.py:10`).
pub fn detect_delimiter(header_line: String) -> Result<String, String> {
    Ok(detect(&header_line).to_string())
}

fn detect(header_line: &str) -> char {
    let mut counts = [0_usize; 4];
    let mut in_quote = false;
    for ch in header_line.chars() {
        if ch == '"' {
            in_quote = !in_quote;
        } else if !in_quote && let Some(i) = DELIMITERS.iter().position(|d| *d == ch) {
            counts[i] += 1;
        }
    }
    // Python `max` keeps the first maximum.
    let mut best = 0;
    for i in 1..DELIMITERS.len() {
        if counts[i] > counts[best] {
            best = i;
        }
    }
    if counts[best] > 0 {
        DELIMITERS[best]
    } else {
        ','
    }
}

/// Port of `preview` (`turbojet/engine/ops/preview.py:23`).
pub fn preview(head_text: String, max_rows: i64) -> Result<String, String> {
    let first_line = head_text
        .split('\n')
        .next()
        .unwrap_or("")
        .trim_end_matches('\r');
    let delimiter = detect(first_line);
    let mut columns: Option<Vec<String>> = None;
    let mut rows: Vec<Vec<String>> = Vec::new();
    let (records, csv_error) = read_records(&head_text, delimiter);
    let mut stopped = false;
    for record in records {
        if record.is_empty() {
            continue;
        }
        if columns.is_none() {
            columns = Some(record);
            continue;
        }
        if i64::try_from(rows.len()).unwrap_or(i64::MAX) >= max_rows {
            stopped = true;
            break;
        }
        rows.push(record);
    }
    if let (Some(e), false) = (csv_error, stopped) {
        return Ok(error_json("CSV_ERROR", &e));
    }
    let mut out = Map::new();
    out.insert("delimiter".into(), delimiter.to_string().into());
    out.insert("columns".into(), columns.unwrap_or_default().into());
    out.insert("rows".into(), rows.into());
    serde_json::to_string(&out).map_err(|e| format!("RuntimeError: {e}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn opts() -> String {
        r#"{"columns":["kota","total"],"group_by":"kota","value_column":"total"}"#.to_string()
    }

    #[test]
    fn decimal_indonesia_and_scale() {
        let out = aggregate_chunk("A,\"1.500,50\"\nA,2\nB,\"-0,00\"\n".into(), opts(), 2).unwrap();
        assert_eq!(
            out,
            r#"{"rows_read":3,"rows_valid":3,"groups":[["A",2,"1502.50"],["B",1,"-0.00"]],"errors":[]}"#
        );
    }

    #[test]
    fn rejects_ambiguous_and_non_ascii() {
        assert_eq!(parse_number("1.5", true).err(), Some("NOT_A_NUMBER"));
        assert_eq!(parse_number("١٢", true).err(), Some("NOT_A_NUMBER"));
        assert_eq!(
            parse_number("1234567890123456", true).err(),
            Some("OUT_OF_RANGE")
        );
    }

    #[test]
    fn csv_quotes_and_blank_lines() {
        let (recs, err) = read_records("a,\"b\nc\"\n\nx\"y,z\r\n", ',');
        assert!(err.is_none());
        assert_eq!(
            recs,
            vec![
                vec!["a".to_string(), "b\nc".into()],
                vec![],
                vec!["x\"y".into(), "z".into()]
            ]
        );
    }

    #[test]
    fn delimiter_first_max_wins() {
        assert_eq!(detect("a;b,c"), ',');
        assert_eq!(detect("a;b;c,d"), ';');
        assert_eq!(detect("\"a,b\""), ',');
    }
}
