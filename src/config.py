from dataclasses import dataclass
from datetime import date, time


@dataclass(frozen=True)
class PrizeSpec:
    name: str
    source_label: str
    count: int
    width: int

    @property
    def columns(self) -> tuple[str, ...]:
        if self.count == 1:
            return (self.name,)
        return tuple(f'{self.name}_{index}' for index in range(1, self.count + 1))


PRIZE_SPECS = (
    PrizeSpec('special', 'ĐB', 1, 6),
    PrizeSpec('prize1', '1', 1, 5),
    PrizeSpec('prize2', '2', 1, 5),
    PrizeSpec('prize3', '3', 2, 5),
    PrizeSpec('prize4', '4', 7, 5),
    PrizeSpec('prize5', '5', 1, 4),
    PrizeSpec('prize6', '6', 3, 4),
    PrizeSpec('prize7', '7', 1, 3),
    PrizeSpec('prize8', '8', 1, 2),
)

PRIZE_COLUMNS = tuple(column for prize in PRIZE_SPECS for column in prize.columns)
PRIZE_WIDTHS = {column: prize.width for prize in PRIZE_SPECS for column in prize.columns}
NUMBER_OF_PRIZES = sum(prize.count for prize in PRIZE_SPECS)


@dataclass(frozen=True)
class RegionConfig:
    code: str
    name: str
    source_url_template: str
    draw_complete_time: time
    prize_specs: tuple[PrizeSpec, ...]
    output_names: dict[str, str]
    province_slugs: dict[str, str]
    schedule_versions: tuple[tuple[date, dict[int, tuple[str, ...]]], ...]
    province_overrides: dict[date, tuple[str, ...]]
    no_draw_ranges: tuple[tuple[date, date], ...]
    prize_width_overrides: tuple[tuple[date, date, dict[str, int]], ...]

    def source_url(self, selected_date: date) -> str:
        return self.source_url_template.format(date=selected_date.strftime('%d-%m-%Y'))

    def expected_provinces(self, selected_date: date) -> tuple[str, ...]:
        if any(first <= selected_date <= last for first, last in self.no_draw_ranges):
            return ()
        if selected_date in self.province_overrides:
            return self.province_overrides[selected_date]

        applicable = [
            schedule for effective_from, schedule in self.schedule_versions if effective_from <= selected_date
        ]
        if not applicable:
            raise ValueError(f'no province schedule configured for region={self.code} date={selected_date}')
        return applicable[-1][selected_date.weekday()]

    def prize_width(self, column: str, selected_date: date) -> int:
        for first, last, overrides in self.prize_width_overrides:
            if first <= selected_date <= last and column in overrides:
                return overrides[column]
        return PRIZE_WIDTHS[column]


XSMN_PROVINCES = {
    'TPHCM': 'tphcm',
    'Đồng Tháp': 'dong-thap',
    'Cà Mau': 'ca-mau',
    'Bến Tre': 'ben-tre',
    'Vũng Tàu': 'vung-tau',
    'Bạc Liêu': 'bac-lieu',
    'Đồng Nai': 'dong-nai',
    'Cần Thơ': 'can-tho',
    'Sóc Trăng': 'soc-trang',
    'An Giang': 'an-giang',
    'Tây Ninh': 'tay-ninh',
    'Bình Thuận': 'binh-thuan',
    'Vĩnh Long': 'vinh-long',
    'Bình Dương': 'binh-duong',
    'Trà Vinh': 'tra-vinh',
    'Long An': 'long-an',
    'Bình Phước': 'binh-phuoc',
    'Hậu Giang': 'hau-giang',
    'Tiền Giang': 'tien-giang',
    'Kiên Giang': 'kien-giang',
    'Đà Lạt': 'da-lat',
}

XSMT_PROVINCES = {
    'Phú Yên': 'phu-yen',
    'Huế': 'hue',
    'Đắk Lắk': 'dak-lak',
    'Quảng Nam': 'quang-nam',
    'Đà Nẵng': 'da-nang',
    'Khánh Hòa': 'khanh-hoa',
    'Quảng Bình': 'quang-binh',
    'Bình Định': 'binh-dinh',
    'Quảng Trị': 'quang-tri',
    'Gia Lai': 'gia-lai',
    'Ninh Thuận': 'ninh-thuan',
    'Quảng Ngãi': 'quang-ngai',
    'Đắk Nông': 'dak-nong',
    'Kon Tum': 'kon-tum',
}

REGIONS = {
    'xsmn': RegionConfig(
        code='xsmn',
        name='Xổ số miền Nam',
        source_url_template='https://xoso.com.vn/xsmn-{date}.html',
        draw_complete_time=time(16, 45),
        prize_specs=PRIZE_SPECS,
        output_names={'raw': 'xsmn', 'two_digits': 'xsmn-2-digits', 'sparse': 'xsmn-sparse'},
        province_slugs=XSMN_PROVINCES,
        schedule_versions=(
            (
                date.min,
                {
                    0: ('TPHCM', 'Đồng Tháp', 'Cà Mau'),
                    1: ('Bến Tre', 'Vũng Tàu', 'Bạc Liêu'),
                    2: ('Đồng Nai', 'Cần Thơ', 'Sóc Trăng'),
                    3: ('An Giang', 'Tây Ninh', 'Bình Thuận'),
                    4: ('Vĩnh Long', 'Bình Dương', 'Trà Vinh'),
                    5: ('TPHCM', 'Long An', 'Bình Phước', 'Hậu Giang'),
                    6: ('Tiền Giang', 'Kiên Giang', 'Đà Lạt'),
                },
            ),
        ),
        province_overrides={},
        no_draw_ranges=(
            (date(2020, 4, 1), date(2020, 4, 28)),
            (date(2021, 7, 9), date(2021, 10, 21)),
        ),
        prize_width_overrides=(),
    ),
    'xsmt': RegionConfig(
        code='xsmt',
        name='Xổ số miền Trung',
        source_url_template='https://xoso.com.vn/xsmt-{date}.html',
        draw_complete_time=time(17, 45),
        prize_specs=PRIZE_SPECS,
        output_names={'raw': 'xsmt', 'two_digits': 'xsmt-2-digits', 'sparse': 'xsmt-sparse'},
        province_slugs=XSMT_PROVINCES,
        schedule_versions=(
            (
                date.min,
                {
                    0: ('Phú Yên', 'Huế'),
                    1: ('Đắk Lắk', 'Quảng Nam'),
                    2: ('Đà Nẵng', 'Khánh Hòa'),
                    3: ('Quảng Bình', 'Bình Định', 'Quảng Trị'),
                    4: ('Gia Lai', 'Ninh Thuận'),
                    5: ('Đà Nẵng', 'Quảng Ngãi', 'Đắk Nông'),
                    6: ('Khánh Hòa', 'Kon Tum'),
                },
            ),
            (
                date(2022, 1, 2),
                {
                    0: ('Phú Yên', 'Huế'),
                    1: ('Đắk Lắk', 'Quảng Nam'),
                    2: ('Đà Nẵng', 'Khánh Hòa'),
                    3: ('Quảng Bình', 'Bình Định', 'Quảng Trị'),
                    4: ('Gia Lai', 'Ninh Thuận'),
                    5: ('Đà Nẵng', 'Quảng Ngãi', 'Đắk Nông'),
                    6: ('Khánh Hòa', 'Kon Tum', 'Huế'),
                },
            ),
        ),
        province_overrides={
            date(2021, 7, 27): ('Quảng Nam',),
            date(2021, 8, 3): ('Quảng Nam',),
            date(2021, 8, 6): ('Gia Lai',),
            date(2021, 8, 18): ('Khánh Hòa',),
            date(2021, 8, 21): ('Quảng Ngãi', 'Đắk Nông'),
            date(2021, 9, 4): ('Đà Nẵng', 'Đắk Nông'),
        },
        no_draw_ranges=(
            (date(2020, 4, 1), date(2020, 4, 23)),
            (date(2021, 7, 28), date(2021, 7, 28)),
            (date(2021, 7, 31), date(2021, 8, 2)),
            (date(2021, 8, 4), date(2021, 8, 4)),
            (date(2021, 8, 7), date(2021, 8, 8)),
        ),
        prize_width_overrides=((date.min, date(2017, 3, 31), {'special': 5}),),
    ),
}
