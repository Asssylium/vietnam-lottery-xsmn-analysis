from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from config import PRIZE_COLUMNS, PRIZE_WIDTHS


class Result(BaseModel):
    model_config = ConfigDict(extra='forbid')

    region: Literal['xsmn', 'xsmt']
    province: str
    province_slug: str
    date: date

    special: str
    prize1: str
    prize2: str
    prize3_1: str
    prize3_2: str
    prize4_1: str
    prize4_2: str
    prize4_3: str
    prize4_4: str
    prize4_5: str
    prize4_6: str
    prize4_7: str
    prize5: str
    prize6_1: str
    prize6_2: str
    prize6_3: str
    prize7: str
    prize8: str

    @field_validator(*PRIZE_COLUMNS)
    @classmethod
    def validate_prize(cls, value: str, info) -> str:
        width = PRIZE_WIDTHS[info.field_name]
        if not isinstance(value, str) or not value.isdigit() or len(value) != width:
            raise ValueError(f'{info.field_name} must contain exactly {width} digits')
        return value

    @property
    def key(self) -> tuple[str, str, date]:
        return self.region, self.province, self.date
