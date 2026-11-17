import json
import logging
import os
import shutil
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd

from config import NUMBER_OF_PRIZES, REGIONS
from dtos import Result
from schemas import (
    RAW_COLUMNS,
    SPARSE_COLUMNS,
    SPARSE_NUMBER_COLUMNS,
    build_dataframes,
    validate_draws,
)

SCHEMA_VERSION = '1.0.0'
DEFAULT_REPOSITORY = 'Asssylium/vietnam-lottery-xsmn-analysis'
LOGGER = logging.getLogger(__name__)


class Lottery:
    def __init__(self, data_dir: str | Path = 'data', repository: str = DEFAULT_REPOSITORY) -> None:
        self.data_dir = Path(data_dir)
        self.repository = repository
        self._data: dict[tuple[str, str, date], Result] = {}
        self._dirty = False
        self._last_update_time: str | None = None

    def load(self) -> None:
        self._data.clear()
        for region in REGIONS:
            json_path = self.data_dir / f'{region}.json'
            if not json_path.exists():
                continue
            payload = json.loads(json_path.read_text(encoding='utf-8'))
            for item in payload:
                result = Result.model_validate(item)
                if result.region != region:
                    raise ValueError(f'{json_path} contains region={result.region!r}')
                if result.key in self._data:
                    raise ValueError(f'duplicate composite key: {result.key!r}')
                self._data[result.key] = result

        manifest_path = self.data_dir / 'manifest.json'
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            self._last_update_time = manifest.get('last_update_time')
        # Existing output may be incomplete because a prior source page omitted a
        # province. Load it so the overlap fetch can repair it before publication.
        validate_draws(self._data.values(), require_complete=False)
        self._dirty = False

    def validate(self) -> None:
        validate_draws(self._data.values())
        build_dataframes(self._data.values())

    def merge(self, results: list[Result]) -> bool:
        pending: dict[tuple[str, str, date], Result] = {}
        for result in results:
            if result.key in pending:
                raise ValueError(f'duplicate fetched composite key: {result.key!r}')
            pending[result.key] = result

        candidate = {**self._data, **pending}
        validate_draws(candidate.values())
        changed = False
        for key, result in pending.items():
            previous = self._data.get(key)
            if previous != result:
                changed = True
                if previous is not None:
                    LOGGER.info(
                        'Correction detected region=%s province=%s date=%s',
                        result.region,
                        result.province,
                        result.date,
                    )
        if changed:
            self._data = candidate
            self._dirty = True
        return changed

    def update(self, result: Result) -> None:
        self.merge([result])

    def get_last_date(self, region: str) -> date | None:
        dates = [result.date for result in self._data.values() if result.region == region]
        return max(dates, default=None)

    def get_raw_data(self) -> pd.DataFrame:
        return build_dataframes(self._data.values())[0]

    def get_2_digits_data(self) -> pd.DataFrame:
        return build_dataframes(self._data.values())[1]

    def get_sparse_data(self) -> pd.DataFrame:
        return build_dataframes(self._data.values())[2]

    @staticmethod
    def _write_formats(base_path: Path, dataframe: pd.DataFrame) -> None:
        base_path.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_csv(base_path.with_suffix('.csv'), index=False, lineterminator='\n')
        dataframe.to_json(
            base_path.with_suffix('.json'),
            orient='records',
            indent=2,
            force_ascii=False,
        )
        dataframe.to_parquet(base_path.with_suffix('.parquet'), index=False)

    def _raw_urls(self, relative_base: str) -> dict[str, str]:
        root = f'https://raw.githubusercontent.com/{self.repository}/refs/heads/main/{relative_base}'
        return {extension: f'{root}.{extension}' for extension in ('csv', 'json', 'parquet')}

    def _feed_urls(self, raw_base: str, two_base: str, sparse_base: str) -> dict[str, dict[str, str]]:
        return {
            'ordered_prizes': self._raw_urls(raw_base),
            'two_digits': self._raw_urls(two_base),
            'sparse': self._raw_urls(sparse_base),
        }

    def _build_manifest(self, raw: pd.DataFrame, last_update_time: str) -> dict:
        regions = []
        for region, config in REGIONS.items():
            regional = raw[raw['region'] == region]
            region_base = f'data/{config.output_names["raw"]}'
            region_two = f'data/{config.output_names["two_digits"]}'
            region_sparse = f'data/{config.output_names["sparse"]}'
            province_entries = []
            for province, slug in config.province_slugs.items():
                province_rows = regional[regional['province'] == province]
                first_date = None if province_rows.empty else str(province_rows['date'].min())
                last_date = None if province_rows.empty else str(province_rows['date'].max())
                province_entries.append(
                    {
                        'region': region,
                        'province': province,
                        'province_slug': slug,
                        'prize_count': NUMBER_OF_PRIZES,
                        'schema_version': SCHEMA_VERSION,
                        'first_date': first_date,
                        'last_date': last_date,
                        'row_count': len(province_rows),
                        'last_update_time': last_update_time,
                        'feed_urls': self._feed_urls(
                            f'data/{region}/{slug}',
                            f'data/{region}/{slug}-2-digits',
                            f'data/{region}/{slug}-sparse',
                        ),
                    }
                )
            regions.append(
                {
                    'region': region,
                    'name': config.name,
                    'prize_count': NUMBER_OF_PRIZES,
                    'schema_version': SCHEMA_VERSION,
                    'draw_complete_time': config.draw_complete_time.isoformat(timespec='minutes'),
                    'first_date': None if regional.empty else str(regional['date'].min()),
                    'last_date': None if regional.empty else str(regional['date'].max()),
                    'row_count': len(regional),
                    'last_update_time': last_update_time,
                    'feed_urls': self._feed_urls(region_base, region_two, region_sparse),
                    'provinces': province_entries,
                }
            )
        return {
            'schema_version': SCHEMA_VERSION,
            'source': 'https://xoso.com.vn/',
            'repository': self.repository,
            'last_update_time': last_update_time,
            'regions': regions,
        }

    def dump(self, updated_at: datetime | None = None) -> None:
        raw, two_digits, sparse = build_dataframes(self._data.values())
        if self._dirty or self._last_update_time is None:
            timestamp = (updated_at or datetime.now(UTC)).astimezone(UTC).isoformat().replace('+00:00', 'Z')
        else:
            timestamp = self._last_update_time

        parent = self.data_dir.parent
        parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f'.{self.data_dir.name}-staging-', dir=parent))
        backup = parent / f'.{self.data_dir.name}-backup-{uuid4().hex}'
        try:
            for region, config in REGIONS.items():
                mask = raw['region'] == region
                regional_raw = raw[mask].reset_index(drop=True)
                regional_two = two_digits[mask].reset_index(drop=True)
                regional_sparse = sparse[mask].reset_index(drop=True)
                self._write_formats(staging / config.output_names['raw'], regional_raw)
                self._write_formats(staging / config.output_names['two_digits'], regional_two)
                self._write_formats(staging / config.output_names['sparse'], regional_sparse)

                for province, slug in config.province_slugs.items():
                    province_mask = regional_raw['province'] == province
                    self._write_formats(staging / region / slug, regional_raw[province_mask].reset_index(drop=True))
                    self._write_formats(
                        staging / region / f'{slug}-2-digits',
                        regional_two[province_mask].reset_index(drop=True),
                    )
                    self._write_formats(
                        staging / region / f'{slug}-sparse',
                        regional_sparse[province_mask].reset_index(drop=True),
                    )

            manifest = self._build_manifest(raw, timestamp)
            (staging / 'manifest.json').write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )

            if self.data_dir.exists():
                os.replace(self.data_dir, backup)
            os.replace(staging, self.data_dir)
            if backup.exists():
                shutil.rmtree(backup)
        except Exception:
            if backup.exists() and not self.data_dir.exists():
                os.replace(backup, self.data_dir)
            raise
        finally:
            if staging.exists():
                shutil.rmtree(staging)

        self._last_update_time = timestamp
        self._dirty = False

    def validate_published_files(self) -> None:
        self.validate()
        manifest_path = self.data_dir / 'manifest.json'
        if not manifest_path.exists():
            raise ValueError('data/manifest.json is missing')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest.get('schema_version') != SCHEMA_VERSION:
            raise ValueError('manifest schema version mismatch')

        for region, config in REGIONS.items():
            bases = [
                (self.data_dir / config.output_names['raw'], None),
                *[(self.data_dir / region / slug, province) for province, slug in config.province_slugs.items()],
            ]
            for raw_base, province in bases:
                two_base = raw_base.with_name(f'{raw_base.name}-2-digits')
                sparse_base = raw_base.with_name(f'{raw_base.name}-sparse')
                for base in (raw_base, two_base, sparse_base):
                    for extension in ('.csv', '.json', '.parquet'):
                        if not base.with_suffix(extension).exists():
                            raise ValueError(f'missing published file: {base.with_suffix(extension)}')

                raw_csv = pd.read_csv(raw_base.with_suffix('.csv'), dtype=str, keep_default_na=False)
                two_csv = pd.read_csv(two_base.with_suffix('.csv'), dtype=str, keep_default_na=False)
                sparse_csv = pd.read_csv(sparse_base.with_suffix('.csv'), dtype=str, keep_default_na=False)
                if raw_csv.columns.tolist() != RAW_COLUMNS or two_csv.columns.tolist() != RAW_COLUMNS:
                    raise ValueError(f'invalid ordered-prize schema: {raw_base}')
                if sparse_csv.columns.tolist() != SPARSE_COLUMNS:
                    raise ValueError(f'invalid sparse schema: {sparse_base}')
                if not sparse_csv.empty:
                    totals = sparse_csv[SPARSE_NUMBER_COLUMNS].astype('int64').sum(axis=1)
                    if not totals.eq(NUMBER_OF_PRIZES).all():
                        raise ValueError(f'sparse row total mismatch: {sparse_base}')
                if province is not None and not raw_csv.empty and set(raw_csv['province']) != {province}:
                    raise ValueError(f'province feed mixes data: {raw_base}')

                expected_rows = len(raw_csv)
                for base in (raw_base, two_base, sparse_base):
                    if len(json.loads(base.with_suffix('.json').read_text(encoding='utf-8'))) != expected_rows:
                        raise ValueError(f'JSON row count mismatch: {base}')
                    if len(pd.read_parquet(base.with_suffix('.parquet'))) != expected_rows:
                        raise ValueError(f'Parquet row count mismatch: {base}')
