import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from config import NUMBER_OF_PRIZES, PRIZE_COLUMNS
from crawler import parse_results_html
from lottery import Lottery
from schemas import KEY_COLUMNS, SPARSE_NUMBER_COLUMNS, validate_draws

FIXTURES = Path(__file__).parent / 'fixtures'
MONDAY = date(2026, 11, 16)


def parsed_results():
    xsmn = (FIXTURES / 'xsmn-multiple-provinces.html').read_text(encoding='utf-8')
    xsmt = (FIXTURES / 'xsmt-multiple-provinces.html').read_text(encoding='utf-8')
    return [
        *parse_results_html(xsmn, 'xsmn', MONDAY),
        *parse_results_html(xsmt, 'xsmt', MONDAY),
    ]


def test_composite_key_allows_provinces_on_same_date_and_rejects_duplicates() -> None:
    results = parsed_results()
    validate_draws(results)
    assert len({result.key for result in results}) == 5

    with pytest.raises(ValueError, match='duplicate composite key'):
        validate_draws([*results, results[0]])


def test_generated_frames_have_18_prizes_and_sparse_totals() -> None:
    lottery = Lottery()
    lottery.merge(parsed_results())

    raw = lottery.get_raw_data()
    sparse = lottery.get_sparse_data()
    assert raw.columns.tolist()[-NUMBER_OF_PRIZES:] == list(PRIZE_COLUMNS)
    assert raw.duplicated(KEY_COLUMNS).sum() == 0
    assert sparse[SPARSE_NUMBER_COLUMNS].sum(axis=1).eq(NUMBER_OF_PRIZES).all()


def test_dump_creates_isolated_province_feeds_in_all_formats(tmp_path: Path) -> None:
    data_dir = tmp_path / 'data'
    lottery = Lottery(data_dir, 'example/lottery')
    lottery.merge(parsed_results())
    lottery.dump(datetime(2026, 11, 16, 12, tzinfo=UTC))
    lottery.validate_published_files()

    tphcm = pd.read_csv(data_dir / 'xsmn' / 'tphcm.csv', dtype=str)
    phu_yen = pd.read_csv(data_dir / 'xsmt' / 'phu-yen.csv', dtype=str)
    assert tphcm['province'].tolist() == ['TPHCM']
    assert phu_yen['province'].tolist() == ['Phú Yên']
    assert tphcm.loc[0, 'prize3_1'] == '01402'
    for extension in ('csv', 'json', 'parquet'):
        assert (data_dir / f'xsmn.{extension}').exists()
        assert (data_dir / f'xsmt-sparse.{extension}').exists()


def test_idempotent_rerun_has_identical_generated_bytes(tmp_path: Path) -> None:
    data_dir = tmp_path / 'data'
    lottery = Lottery(data_dir, 'example/lottery')
    lottery.merge(parsed_results())
    lottery.dump(datetime(2026, 11, 16, 12, tzinfo=UTC))
    before = {
        path.relative_to(data_dir): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in data_dir.rglob('*')
        if path.is_file()
    }

    lottery.dump(datetime(2026, 11, 17, 12, tzinfo=UTC))
    after = {
        path.relative_to(data_dir): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in data_dir.rglob('*')
        if path.is_file()
    }

    assert after == before


def test_merge_detects_correction_but_same_rerun_is_noop() -> None:
    lottery = Lottery()
    results = parsed_results()

    assert lottery.merge(results)
    assert not lottery.merge(results)
    corrected = results[0].model_copy(update={'special': '000001'})
    assert lottery.merge([corrected])
    assert lottery.get_raw_data().query("province == 'TPHCM'")['special'].item() == '000001'


def test_overlap_merge_can_repair_an_existing_missing_province(tmp_path: Path) -> None:
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    results = parsed_results()
    incomplete_xsmn = [result.model_dump(mode='json') for result in results[:2]]
    (data_dir / 'xsmn.json').write_text(json.dumps(incomplete_xsmn, ensure_ascii=False), encoding='utf-8')

    lottery = Lottery(data_dir)
    lottery.load()
    assert lottery.merge(results)
    lottery.validate()
