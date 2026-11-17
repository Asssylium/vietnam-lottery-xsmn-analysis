from datetime import date
from pathlib import Path

import pytest

from config import PRIZE_COLUMNS
from crawler import DataValidationError, parse_results_html

FIXTURES = Path(__file__).parent / 'fixtures'
MONDAY = date(2026, 11, 16)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding='utf-8')


def test_xsmn_page_parses_multiple_provinces() -> None:
    results = parse_results_html(fixture('xsmn-multiple-provinces.html'), 'xsmn', MONDAY)

    assert [result.province for result in results] == ['TPHCM', 'Đồng Tháp', 'Cà Mau']
    assert all(len([getattr(result, column) for column in PRIZE_COLUMNS]) == 18 for result in results)


def test_xsmt_page_parses_multiple_provinces() -> None:
    results = parse_results_html(fixture('xsmt-multiple-provinces.html'), 'xsmt', MONDAY)

    assert [result.province for result in results] == ['Phú Yên', 'Huế']
    assert all(len([getattr(result, column) for column in PRIZE_COLUMNS]) == 18 for result in results)


def test_prizes_are_in_published_order_and_keep_leading_zeroes() -> None:
    tphcm = parse_results_html(fixture('xsmn-multiple-provinces.html'), 'xsmn', MONDAY)[0]

    assert [getattr(tphcm, column) for column in PRIZE_COLUMNS] == [
        '733823',
        '88467',
        '46554',
        '01402',
        '61422',
        '91328',
        '05353',
        '83467',
        '52765',
        '15898',
        '58105',
        '68568',
        '6831',
        '6495',
        '6538',
        '1417',
        '175',
        '96',
    ]
    hue = parse_results_html(fixture('xsmt-multiple-provinces.html'), 'xsmt', MONDAY)[1]
    assert hue.special == '850219'
    assert hue.prize3_1 == '01732'
    assert hue.prize8 == '06'


def test_missing_province_section_fails() -> None:
    html = fixture('xsmn-multiple-provinces.html').replace(
        '<th class="prize-col3"><h3><a href="/xo-so-ca-mau/xscm-p1.html">Cà Mau</a></h3></th>',
        '',
    )

    with pytest.raises(DataValidationError, match=r'province_sections.*expected_count=3 actual_count=2'):
        parse_results_html(html, 'xsmn', MONDAY)


def test_incorrect_prize_count_fails() -> None:
    html = fixture('xsmt-multiple-provinces.html').replace(
        '<span class="xs_prize1">19103</span>',
        '',
    )

    with pytest.raises(DataValidationError, match=r'province=Phú Yên.*item=prize4.*expected_count=7 actual_count=6'):
        parse_results_html(html, 'xsmt', MONDAY)


def test_empty_or_unrelated_page_fails() -> None:
    with pytest.raises(DataValidationError, match=r'item=result_table.*expected_count=1 actual_count=0'):
        parse_results_html('<html><table class="table-loto"></table></html>', 'xsmn', MONDAY)


def test_province_results_are_not_mixed() -> None:
    results = parse_results_html(fixture('xsmn-multiple-provinces.html'), 'xsmn', MONDAY)

    assert [(result.province, result.special, result.prize8) for result in results] == [
        ('TPHCM', '733823', '96'),
        ('Đồng Tháp', '050747', '54'),
        ('Cà Mau', '120781', '60'),
    ]
