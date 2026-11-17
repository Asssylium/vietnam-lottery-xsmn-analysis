from collections import defaultdict
from collections.abc import Iterable
from datetime import date

import pandas as pd

from config import NUMBER_OF_PRIZES, PRIZE_COLUMNS, REGIONS
from dtos import Result

KEY_COLUMNS = ['region', 'province', 'date']
METADATA_COLUMNS = ['region', 'province', 'province_slug', 'date']
RAW_COLUMNS = [*METADATA_COLUMNS, *PRIZE_COLUMNS]
SPARSE_NUMBER_COLUMNS = [f'{number:02d}' for number in range(100)]
SPARSE_COLUMNS = [*METADATA_COLUMNS, *SPARSE_NUMBER_COLUMNS]


def validate_draws(draws: Iterable[Result], *, require_complete: bool = True) -> None:
    draw_list = list(draws)
    keys = [draw.key for draw in draw_list]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate composite key (region, province, date)')

    grouped: dict[tuple[str, object], set[str]] = defaultdict(set)
    for draw in draw_list:
        config = REGIONS[draw.region]
        expected_slug = config.province_slugs.get(draw.province)
        if expected_slug != draw.province_slug:
            raise ValueError(
                f'region={draw.region} province={draw.province} date={draw.date} '
                f'expected_slug={expected_slug!r} actual_slug={draw.province_slug!r}'
            )
        expected_for_day = config.expected_provinces(draw.date)
        if draw.province not in expected_for_day:
            raise ValueError(
                f'region={draw.region} province={draw.province} date={draw.date} '
                'province is not scheduled for this weekday'
            )
        grouped[(draw.region, draw.date)].add(draw.province)

    if require_complete:
        for (region, selected_date), actual in grouped.items():
            expected = set(REGIONS[region].expected_provinces(selected_date))
            if actual != expected:
                raise ValueError(
                    f'region={region} province={sorted(expected - actual)!r} date={selected_date} '
                    f'expected_count={len(expected)} actual_count={len(actual)}'
                )


def build_dataframes(draws: Iterable[Result]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    draw_list = list(draws)
    validate_draws(draw_list)
    rows = [draw.model_dump(mode='json') for draw in draw_list]
    raw = pd.DataFrame(rows, columns=RAW_COLUMNS)
    raw = raw.astype({column: 'string' for column in RAW_COLUMNS})
    if not raw.empty:
        raw = raw.sort_values(['date', 'region', 'province'], kind='stable', ignore_index=True)

    two_digits = raw.copy()
    for column in PRIZE_COLUMNS:
        two_digits[column] = two_digits[column].str[-2:]

    sparse_rows = []
    for row in two_digits.to_dict(orient='records'):
        sparse_row = {column: row[column] for column in METADATA_COLUMNS}
        counts = {column: 0 for column in SPARSE_NUMBER_COLUMNS}
        for column in PRIZE_COLUMNS:
            counts[row[column]] += 1
        sparse_rows.append({**sparse_row, **counts})
    sparse = pd.DataFrame(sparse_rows, columns=SPARSE_COLUMNS)
    sparse = sparse.astype(
        {
            **{column: 'string' for column in METADATA_COLUMNS},
            **{column: 'int64' for column in SPARSE_NUMBER_COLUMNS},
        }
    )
    validate_dataframes(raw, two_digits, sparse)
    return raw, two_digits, sparse


def validate_dataframes(raw: pd.DataFrame, two_digits: pd.DataFrame, sparse: pd.DataFrame) -> None:
    if raw.columns.tolist() != RAW_COLUMNS:
        raise ValueError(f'invalid raw columns: {raw.columns.tolist()!r}')
    if two_digits.columns.tolist() != RAW_COLUMNS:
        raise ValueError(f'invalid two-digit columns: {two_digits.columns.tolist()!r}')
    if sparse.columns.tolist() != SPARSE_COLUMNS:
        raise ValueError(f'invalid sparse columns: {sparse.columns.tolist()!r}')

    if (
        raw.duplicated(KEY_COLUMNS).any()
        or two_digits.duplicated(KEY_COLUMNS).any()
        or sparse.duplicated(KEY_COLUMNS).any()
    ):
        raise ValueError('duplicate composite key (region, province, date)')
    for column in PRIZE_COLUMNS:
        valid_raw = [
            value.isdigit() and len(value) == REGIONS[region].prize_width(column, date.fromisoformat(selected_date))
            for region, selected_date, value in raw[['region', 'date', column]].itertuples(index=False, name=None)
        ]
        if not all(valid_raw):
            raise ValueError(f'raw column {column} contains an invalid historical digit width')
        if not two_digits[column].str.fullmatch(r'\d{2}').all():
            raise ValueError(f'two-digit column {column} must contain exactly 2 digits')
    if not sparse[SPARSE_NUMBER_COLUMNS].sum(axis=1).eq(NUMBER_OF_PRIZES).all():
        raise ValueError(f'each sparse row must sum to exactly {NUMBER_OF_PRIZES}')

    expected_order = raw.sort_values(['date', 'region', 'province'], kind='stable').index.tolist()
    if expected_order != raw.index.tolist():
        raise ValueError('rows must be sorted by date, region, and province')
