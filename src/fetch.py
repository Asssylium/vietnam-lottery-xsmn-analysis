import argparse
import logging
import os
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from config import REGIONS
from crawler import Crawler, DataValidationError
from lottery import DEFAULT_REPOSITORY, Lottery

TIMEZONE = ZoneInfo('Asia/Ho_Chi_Minh')
LOGGER = logging.getLogger(__name__)


def parse_date(value: str):
    return datetime.strptime(value, '%Y-%m-%d').date()


def date_range(start, end):
    for offset in range((end - start).days + 1):
        yield start + timedelta(days=offset)


def batches(items: list[tuple[str, date]], size: int) -> Iterable[list[tuple[str, date]]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def fetch_batch(requests: list[tuple[str, date]]) -> tuple[int, list]:
    results = []
    with Crawler() as crawler:
        for region, selected_date in requests:
            LOGGER.debug('Fetching region=%s date=%s', region, selected_date)
            try:
                results.extend(crawler.fetch(region, selected_date))
            except Exception:
                LOGGER.exception('Fetch failed region=%s province=* date=%s', region, selected_date)
                raise
    return len(requests), results


def fetch_all(requests: list[tuple[str, date]], workers: int, batch_size: int) -> list:
    if workers == 1:
        _, results = fetch_batch(requests)
        return results

    pending = []
    completed = 0
    request_batches = list(batches(requests, batch_size))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(fetch_batch, batch) for batch in request_batches]
        try:
            for future in as_completed(futures):
                request_count, results = future.result()
                pending.extend(results)
                completed += request_count
                LOGGER.info('Backfill progress completed_pages=%d total_pages=%d', completed, len(requests))
        except Exception:
            for future in futures:
                future.cancel()
            raise
    return pending


def latest_complete_date(region: str, now: datetime):
    config = REGIONS[region]
    local_now = now.astimezone(TIMEZONE)
    if local_now.time() < config.draw_complete_time:
        return local_now.date() - timedelta(days=1)
    return local_now.date()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Publish validated XSMN and XSMT lottery feeds.')
    parser.add_argument('--regions', nargs='+', choices=REGIONS, default=list(REGIONS))
    parser.add_argument('--date', type=parse_date, help='Fetch exactly one historical draw date.')
    parser.add_argument('--start-date', type=parse_date)
    parser.add_argument('--end-date', type=parse_date)
    parser.add_argument('--overlap-days', type=int, default=3)
    parser.add_argument(
        '--workers', type=int, default=1, help='Concurrent source workers; use a small value for backfills.'
    )
    parser.add_argument('--batch-size', type=int, default=50, help='Dates fetched sequentially per worker session.')
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument(
        '--github-repository',
        default=os.environ.get('GITHUB_REPOSITORY', DEFAULT_REPOSITORY),
        help='owner/repository used to construct manifest feed URLs.',
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.overlap_days < 1:
        raise ValueError('--overlap-days must be at least 1')
    if args.workers < 1:
        raise ValueError('--workers must be at least 1')
    if args.batch_size < 1:
        raise ValueError('--batch-size must be at least 1')
    if args.date and (args.start_date or args.end_date):
        raise ValueError('--date cannot be combined with --start-date or --end-date')

    lottery = Lottery(args.data_dir, args.github_repository)
    lottery.load()
    now = datetime.now(TIMEZONE)
    requests = []
    for region in args.regions:
        if args.date:
            dates = [args.date]
        else:
            end = args.end_date or latest_complete_date(region, now)
            previous = lottery.get_last_date(region)
            default_start = end - timedelta(days=args.overlap_days - 1)
            start = args.start_date or (
                min(default_start, previous - timedelta(days=args.overlap_days - 1)) if previous else default_start
            )
            dates = date_range(start, end)
        requests.extend((region, selected_date) for selected_date in dates)

    try:
        pending = fetch_all(requests, args.workers, args.batch_size)
    except DataValidationError:
        LOGGER.exception('Backfill validation failed; no fetched results were merged or published')
        raise

    changed = lottery.merge(pending)
    lottery.dump(updated_at=now if changed else None)
    lottery.validate_published_files()
    LOGGER.info('Published %d fetched draws; changed=%s', len(pending), changed)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    main()
