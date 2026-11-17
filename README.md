# Vietnam XSMN/XSMT province data feeds

This repository publishes validated, province-level traditional lottery results for:

- **XSMN (southern Vietnam):** TPHCM, Đồng Tháp, Cà Mau, Bến Tre, Vũng Tàu, Bạc Liêu, Đồng Nai, Cần Thơ, Sóc Trăng, An Giang, Tây Ninh, Bình Thuận, Vĩnh Long, Bình Dương, Trà Vinh, Long An, Bình Phước, Hậu Giang, Tiền Giang, Kiên Giang, and Đà Lạt.
- **XSMT (central Vietnam):** Phú Yên, Huế, Đắk Lắk, Quảng Nam, Đà Nẵng, Khánh Hòa, Quảng Bình, Bình Định, Quảng Trị, Gia Lai, Ninh Thuận, Quảng Ngãi, Đắk Nông, and Kon Tum.

One row is one `(region, province, date)` draw. Provinces are never combined into an artificial regional result.

## Source and schedule

The publisher reads the province-column result table from:

- `https://xoso.com.vn/xsmn-DD-MM-YYYY.html`
- `https://xoso.com.vn/xsmt-DD-MM-YYYY.html`

The source says XSMN drawing begins at 16:15 and XSMT at 17:15 (Asia/Ho_Chi_Minh). The publisher treats results as complete after 16:45 and 17:45 respectively. GitHub Actions runs daily at 18:00 Asia/Ho_Chi_Minh (`11:00 UTC`), re-fetches a three-day overlap, validates every expected weekday province, and atomically replaces generated output only after all pages pass.

### Weekly province schedule

| Day | XSMN | XSMT |
|---|---|---|
| Monday | TPHCM, Đồng Tháp, Cà Mau | Phú Yên, Huế |
| Tuesday | Bến Tre, Vũng Tàu, Bạc Liêu | Đắk Lắk, Quảng Nam |
| Wednesday | Đồng Nai, Cần Thơ, Sóc Trăng | Đà Nẵng, Khánh Hòa |
| Thursday | An Giang, Tây Ninh, Bình Thuận | Quảng Bình, Bình Định, Quảng Trị |
| Friday | Vĩnh Long, Bình Dương, Trà Vinh | Gia Lai, Ninh Thuận |
| Saturday | TPHCM, Long An, Bình Phước, Hậu Giang | Đà Nẵng, Quảng Ngãi, Đắk Nông |
| Sunday | Tiền Giang, Kiên Giang, Đà Lạt | Khánh Hòa, Kon Tum, Huế |

## Schemas

All CSV, JSON, and Parquet variants use the same logical columns. Raw prize values are strings so leading zeros are preserved.

### Ordered-prize (raw)

Metadata columns:

| Column | Type | Meaning |
|---|---|---|
| `region` | string | `xsmn` or `xsmt` |
| `province` | string | Source province display name |
| `province_slug` | string | Stable ASCII path slug |
| `date` | `YYYY-MM-DD` string | Draw date in Asia/Ho_Chi_Minh |

Prize columns, in published order:

| Prize | Columns | Results | Width |
|---|---|---:|---:|
| Special | `special` | 1 | 6 (historical XSMT rows through 2017-03-31 use the source's five-digit format) |
| Prize 1 | `prize1` | 1 | 5 |
| Prize 2 | `prize2` | 1 | 5 |
| Prize 3 | `prize3_1`, `prize3_2` | 2 | 5 |
| Prize 4 | `prize4_1` … `prize4_7` | 7 | 5 |
| Prize 5 | `prize5` | 1 | 4 |
| Prize 6 | `prize6_1` … `prize6_3` | 3 | 4 |
| Prize 7 | `prize7` | 1 | 3 |
| Prize 8 | `prize8` | 1 | 2 |

Every row therefore contains exactly 18 ordered prize values.

### Two-digit

The two-digit schema has the same metadata and 18 prize columns. Every prize value is a zero-padded two-character string containing the final two digits of the raw result.

### Sparse

The sparse schema has the four metadata columns followed by integer columns `00` through `99`. Each cell is that two-digit value's frequency among the 18 prize positions. Every row sums to exactly 18.

Rows are unique by `(region, province, date)` and sorted by date, region, then province.

## Combined feeds

The workflow writes the repository name into [the manifest](data/manifest.json) through `GITHUB_REPOSITORY`.

| Region | Feed | CSV | JSON | Parquet |
|---|---|---|---|---|
| XSMN | Ordered prizes | `https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/xsmn.csv` | `https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/xsmn.json` | `https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/xsmn.parquet` |
| XSMN | Two digits | `https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/xsmn-2-digits.csv` | `https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/xsmn-2-digits.json` | `https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/xsmn-2-digits.parquet` |
| XSMN | Sparse | `https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/xsmn-sparse.csv` | `https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/xsmn-sparse.json` | `https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/xsmn-sparse.parquet` |
| XSMT | Ordered prizes | `https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/xsmt.csv` | `https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/xsmt.json` | `https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/xsmt.parquet` |
| XSMT | Two digits | `https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/xsmt-2-digits.csv` | `https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/xsmt-2-digits.json` | `https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/xsmt-2-digits.parquet` |
| XSMT | Sparse | `https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/xsmt-sparse.csv` | `https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/xsmt-sparse.json` | `https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/xsmt-sparse.parquet` |

Province feeds follow these patterns:

```text
https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/{region}/{province-slug}.csv
https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/{region}/{province-slug}-2-digits.csv
https://raw.githubusercontent.com/Asssylium/vietnam-lottery-xsmn-analysis/refs/heads/main/data/{region}/{province-slug}-sparse.csv
```

Change the suffix to `.json` or `.parquet` for those formats. Examples are `data/xsmn/tphcm.csv` and `data/xsmt/phu-yen.csv`.

The machine-readable [manifest](data/manifest.json) reports schema version, region, province, prize count, first/last dates, row counts, last update time, and every feed URL.

## Local update and validation

Python 3.15 and [uv](https://docs.astral.sh/uv/) are required.

```sh
uv sync --frozen
uv run --frozen --group testing pytest
uv run --frozen src/fetch.py --date 2026-11-16 --github-repository Asssylium/vietnam-lottery-xsmn-analysis
uv run --frozen src/validate.py
```

For the normal overlap update:

```sh
uv run --frozen src/fetch.py --overlap-days 3 --github-repository Asssylium/vietnam-lottery-xsmn-analysis
```

For a bounded historical backfill, supply an inclusive range. A small worker count reuses one source session per batch while publication remains all-or-nothing:

```sh
uv run --frozen src/fetch.py --start-date 2016-11-17 --end-date 2026-11-16 --workers 8 --batch-size 50 --github-repository Asssylium/vietnam-lottery-xsmn-analysis
```

## Source limitations

- xoso.com.vn is a third-party HTML source, not an official lottery-company API. Results should be checked against the issuing lottery company for legal or financial use.
- The parser intentionally fails if the result table, province schedule, prize counts, or digit widths change. This prevents an empty or redesigned page from being published silently.
- The configured weekday schedule reflects the verified source schedule. Holidays, one-off postponements, renames, and future schedule changes require a reviewed configuration update; the publisher never invents missing province rows.
- Historical configuration includes XSMT's five-digit special prizes through 2017-03-31, the source-verified 2020 and 2021 suspension dates, reduced-province XSMT draws during 2021, and the addition of Huế to the Sunday XSMT schedule from 2022-01-02.
- The three-day overlap detects recent corrections. Corrections older than that require a manual historical re-fetch with `--date` or `--start-date`.
