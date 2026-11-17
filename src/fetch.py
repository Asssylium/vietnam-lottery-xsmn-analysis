import argparse
import logging
import os
from datetime import datetime, timedelta
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
    if args.date and (args.start_date or args.end_date):
        raise ValueError('--date cannot be combined with --start-date or --end-date')

    lottery = Lottery(args.data_dir, args.github_repository)
    lottery.load()
    now = datetime.now(TIMEZONE)
    pending = []
    with Crawler() as crawler:
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

            for selected_date in dates:
                LOGGER.info('Fetching region=%s date=%s', region, selected_date)
                try:
                    pending.extend(crawler.fetch(region, selected_date))
                except DataValidationError:
                    LOGGER.exception('Validation failed while fetching region=%s date=%s', region, selected_date)
                    raise

    changed = lottery.merge(pending)
    lottery.dump(updated_at=now if changed else None)
    lottery.validate_published_files()
    LOGGER.info('Published %d fetched draws; changed=%s', len(pending), changed)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    main()
