# Rust migration plan: turbojet (Python)

1 package, 36 source files (1211 lines), 3 test files, 0 UI files, grouped into 16 units.

| Ready | Caution | Blocked | Keep in source language |
| ---: | ---: | ---: | ---: |
| 7 | 9 | 0 | 0 |

## Start here

Best first ports: safe to port (readiness) and worth porting (loops and string work, tests, size).

| # | Unit | Lines | Priority | Readiness | Tests | Bridge | Main risks |
| ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | `turbojet/engine/ops/` | 176 | 78 | 81 | 1 | PyO3 | String offsets and slicing (3); Dynamic typing (12); Class inheritance (2) |
| 2 | `turbojet/` | 57 | 71 | 99 | 0 | PyO3 | - |
| 3 | `bench/` | 48 | 66 | 97 | 0 | PyO3 | Division and modulo (2); Dynamic typing (1); Clock and random numbers (1) |
| 4 | `turbojet/engine/` | 291 | 66 | 68 | 1 | PyO3 | String offsets and slicing (1); Dynamic typing (22); Generators (8) |

### `turbojet/engine/ops/`

176 lines in 3 files, wave 0, priority 78, readiness 81, bridge **PyO3**.

- Leaf: imports no other unit.
- 1 test file imports it directly.
- String offsets and slicing x3: `turbojet/engine/ops/group_sum.py:49`, `turbojet/engine/ops/group_sum.py:51`, `turbojet/engine/ops/group_sum.py:142`
- Dynamic typing x12: `turbojet/engine/ops/__init__.py:14`, `turbojet/engine/ops/__init__.py:18`, `turbojet/engine/ops/__init__.py:21`
- Class inheritance x2: `turbojet/engine/ops/group_sum.py:37`, `turbojet/engine/ops/group_sum.py:41`
- Exceptions x10: `turbojet/engine/ops/__init__.py:16`, `turbojet/engine/ops/group_sum.py:79`, `turbojet/engine/ops/group_sum.py:96`

### `turbojet/`

57 lines in 3 files, wave 0, priority 71, readiness 99, bridge **PyO3**.

- 1 PyPI dependencies not in the crate table: check them by hand.
- Leaf: imports no other unit.

### `bench/`

48 lines in 1 file, wave 2, priority 66, readiness 97, bridge **PyO3**.

- Division and modulo x2: `bench/bench_group_sum.py:26`, `bench/bench_group_sum.py:28`
- Dynamic typing x1: `bench/bench_group_sum.py:18`
- Clock and random numbers x1: `bench/bench_group_sum.py:19`

### `turbojet/engine/`

291 lines in 5 files, wave 1, priority 66, readiness 68, bridge **PyO3**.

- 1 test file imports it directly.
- String offsets and slicing x1: `turbojet/engine/runner.py:104`
- Dynamic typing x22: `turbojet/engine/contract.py:30`, `turbojet/engine/contract.py:36`, `turbojet/engine/contract.py:40`
- Generators x8: `turbojet/engine/csvio.py:31`, `turbojet/engine/csvio.py:31`, `turbojet/engine/csvio.py:34`
- Class inheritance x2: `turbojet/engine/contract.py:26`, `turbojet/engine/runner.py:28`
- Integer width and overflow x1: `turbojet/engine/contract.py:67`
- Division and modulo x1: `turbojet/engine/csvio.py:28`
- Exceptions x17: `turbojet/engine/contract.py:32`, `turbojet/engine/contract.py:35`, `turbojet/engine/contract.py:37`

## Order by package

Packages come after the workspace packages they use. Inside a package, port by wave: a unit's imports are in earlier waves.

### 1. turbojet (`.`, portable, 3 test files)

| Wave | Unit | Status | Lines | Readiness | Bridge | Main risks |
| ---: | --- | --- | ---: | ---: | --- | --- |
| 0 | `turbojet/config/` | ready | 0 | 100 | PyO3 | - |
| 0 | `turbojet/turbojet/` | ready | 0 | 100 | PyO3 | - |
| 0 | `turbojet/turbojet/doctype/` | ready | 0 | 100 | PyO3 | - |
| 0 | `turbojet/` | ready | 57 | 99 | PyO3 | - |
| 0 | `turbojet/turbojet/doctype/turbojet_job/` | caution | 3 | 98 | PyO3 | Class inheritance (1) |
| 0 | `turbojet/turbojet/doctype/turbojet_plan/` | caution | 3 | 98 | PyO3 | Class inheritance (1) |
| 0 | `turbojet/turbojet/doctype/turbojet_plan_limit/` | caution | 3 | 98 | PyO3 | Class inheritance (1) |
| 0 | `turbojet/turbojet/doctype/turbojet_quota_balance/` | caution | 3 | 98 | PyO3 | Class inheritance (1) |
| 0 | `turbojet/turbojet/doctype/turbojet_settings/` | caution | 3 | 98 | PyO3 | Class inheritance (1) |
| 0 | `turbojet/turbojet/doctype/turbojet_usage_entry/` | caution | 8 | 98 | PyO3 | Class inheritance (1) |
| 0 | `turbojet/engine/ops/` | ready | 176 | 81 | PyO3 | String offsets and slicing (3); Dynamic typing (12) |
| 1 | `turbojet/engine/` | ready | 291 | 68 | PyO3 | String offsets and slicing (1); Dynamic typing (22) |
| 2 | `bench/` | ready | 48 | 97 | PyO3 | Division and modulo (2); Dynamic typing (1) |
| 2 | `turbojet/services/` | caution | 528 | 48 | PyO3 | String offsets and slicing (3); Hash iteration order (3) |
| 3 | `turbojet/turbojet/doctype/turbojet_idempotency_key/` | caution | 5 | 98 | PyO3 | Class inheritance (1) |
| 3 | `turbojet/api/` | caution | 83 | 85 | PyO3 | Hash iteration order (2); Dynamic typing (6) |

## PyPI dependencies

| Package | Units | Rust | Fit | Note |
| --- | ---: | --- | --- | --- |
| `frappe` | 10 | ? | unknown |  |

## Risk guide

- **String offsets and slicing** (High): JS indexes strings in UTF-16 code units, Rust in UTF-8 bytes. Offsets that cross the boundary must be converted, or non-ASCII text gets wrong ranges silently.
- **Dynamic typing** (Medium): Values whose shape is checked at runtime need an explicit Rust enum or `serde_json::Value`.
- **Exceptions** (Low): Thrown errors become `Result`. Errors crossing the bridge must map back to the same JS error shape.
- **Generators** (Medium): Lazy generators become iterators, or return a collected Vec across the bridge.
- **Class inheritance** (Medium): Class hierarchies become traits plus composition; `instanceof` checks become enums.
- **Number semantics** (Low): JS numbers are f64; bitwise ops truncate to i32; parseInt is lenient. Pick Rust integer types deliberately. Printing differs: `${n}` gives `1e+21`, `1e-7` and `0` for -0 where Rust's `{}` does not, so use `js::number_to_string`. `Math.round` rounds halves up (-2.5 gives -2), Rust's `round` away from zero: use `js::math_round`. `toFixed` rounds exact halves up ((2.5).toFixed(0) is "3"), Rust's `{:.0}` to even.
- **Integer width and overflow** (Medium): Python ints never overflow; C, Go and Java ints wrap or are undefined on overflow. Pick i64, i128 or a bignum crate deliberately, and use wrapping_* where the source wraps.
- **Division and modulo** (Medium): Python `//` and `%` floor toward negative infinity; Rust `/` and `%` truncate: use `div_euclid`/`rem_euclid` or explicit floor math. C division by zero is undefined.
- **Hash iteration order** (High): Set and map iteration order comes from the source language's hash function. A port cannot reproduce it: sort before output, or make the order part of the contract.
- **Clock and random numbers** (Low): Results that depend on the time or on random numbers differ on every run, so a plain recording cannot pin them down. Record with `record --pin-clock` (TS/JS with the napi bridge, Python): `Date.now()`, `new Date()` and `Math.random` (`time.time`, `datetime.now` and `random`) then return fixed values during record, diff and gate, and the port reads the same ones from `src/port/pinned.rs` (`now_ms()`, `random()`, a documented mulberry32). Or pass the time and the seed in as parameters.
