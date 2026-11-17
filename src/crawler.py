from contextlib import AbstractContextManager
from datetime import date
from typing import Self

from bs4 import BeautifulSoup
from cloudscraper import CloudScraper
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from config import REGIONS, RegionConfig
from dtos import Result

REQUEST_TIMEOUT = 30


class DataValidationError(ValueError):
    def __init__(
        self,
        *,
        region: str,
        province: str,
        selected_date: date,
        item: str,
        expected: int,
        actual: int,
        detail: str = '',
    ) -> None:
        self.region = region
        self.province = province
        self.selected_date = selected_date
        self.item = item
        self.expected = expected
        self.actual = actual
        suffix = f' ({detail})' if detail else ''
        super().__init__(
            f'region={region} province={province} date={selected_date.isoformat()} item={item} '
            f'expected_count={expected} actual_count={actual}{suffix}'
        )


def parse_results_html(html: str, region: str, selected_date: date) -> list[Result]:
    config = REGIONS[region]
    soup = BeautifulSoup(html, 'lxml')
    tables = soup.select('table.table-result.table-xsmn')
    if len(tables) != 1:
        raise DataValidationError(
            region=region,
            province='*',
            selected_date=selected_date,
            item='result_table',
            expected=1,
            actual=len(tables),
        )

    table = tables[0]
    province_names = tuple(header.get_text(' ', strip=True) for header in table.select('thead tr th:not(.name-prize)'))
    expected_provinces = config.expected_provinces(selected_date)
    if province_names != expected_provinces:
        missing = sorted(set(expected_provinces) - set(province_names))
        unexpected = sorted(set(province_names) - set(expected_provinces))
        raise DataValidationError(
            region=region,
            province=','.join(missing or unexpected) or '*',
            selected_date=selected_date,
            item='province_sections',
            expected=len(expected_provinces),
            actual=len(province_names),
            detail=f'expected={expected_provinces!r} actual={province_names!r}',
        )

    rows: dict[str, list] = {}
    for row in table.select('tbody tr'):
        label = row.find('th')
        if label is not None:
            rows[label.get_text(strip=True)] = row.find_all('td', recursive=False)

    results: list[Result] = []
    for province_index, province in enumerate(province_names):
        values: dict[str, str] = {}
        for prize in config.prize_specs:
            cells = rows.get(prize.source_label, [])
            cell = cells[province_index] if province_index < len(cells) else None
            numbers = [] if cell is None else [node.get_text(strip=True) for node in cell.select('span.xs_prize1')]
            if len(numbers) != prize.count:
                raise DataValidationError(
                    region=region,
                    province=province,
                    selected_date=selected_date,
                    item=prize.name,
                    expected=prize.count,
                    actual=len(numbers),
                )
            for column, number in zip(prize.columns, numbers, strict=True):
                if not number.isdigit() or len(number) != prize.width:
                    raise DataValidationError(
                        region=region,
                        province=province,
                        selected_date=selected_date,
                        item=column,
                        expected=prize.width,
                        actual=len(number),
                        detail='digit width',
                    )
                values[column] = number

        results.append(
            Result(
                region=region,
                province=province,
                province_slug=config.province_slugs[province],
                date=selected_date,
                **values,
            )
        )
    return results


class Crawler(AbstractContextManager['Crawler']):
    def __enter__(self) -> Self:
        self._http: CloudScraper = CloudScraper()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._http.close()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_not_exception_type(DataValidationError),
        reraise=True,
    )
    def fetch(self, region: str, selected_date: date) -> list[Result]:
        config: RegionConfig = REGIONS[region]
        response = self._http.get(config.source_url(selected_date), timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return parse_results_html(response.text, region, selected_date)
