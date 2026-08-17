import html
import logging
import re
from datetime import datetime

from app.errors import bad_neis_response
from app.models.internal import (
    Calorie,
    IngredientOrigin,
    Meal,
    Nutrient,
    SchoolSummary,
)
from app.models.neis import NeisMeal, NeisSchool
from app.observability import log_event

logger = logging.getLogger(__name__)
_BR = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]*>")
_CALORIE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*kcal\s*$", re.IGNORECASE)
_NUTRIENT_WITH_UNIT = re.compile(
    r"^\s*(?P<name>[^:()]+?)\s*\((?P<unit>[^()]+)\)\s*:\s*"
    r"(?P<amount>\d+(?:\.\d+)?)\s*$"
)
_NUTRIENT_TRAILING_UNIT = re.compile(
    r"^\s*(?P<name>[^:]+?)\s*:\s*(?P<amount>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>\S+)\s*$"
)


def _clean_text(value: str) -> str:
    unescaped = html.unescape(_TAG.sub("", value))
    without_encoded_tags = _TAG.sub("", unescaped)
    return without_encoded_tags.replace("<", "").replace(">", "").strip()


def split_br(value: str | None) -> list[str]:
    if not value:
        return []
    return [
        cleaned
        for part in _BR.split(value)
        if (cleaned := _clean_text(part))
    ]


def map_school(row: NeisSchool) -> SchoolSummary:
    address_parts = [
        part.strip()
        for part in (row.ORG_RDNMA, row.ORG_RDNDA)
        if part and part.strip()
    ]
    return SchoolSummary(
        education_office_code=row.ATPT_OFCDC_SC_CODE,
        education_office_name=row.ATPT_OFCDC_SC_NM,
        school_code=row.SD_SCHUL_CODE,
        name=row.SCHUL_NM,
        school_type=row.SCHUL_KND_SC_NM,
        region=row.LCTN_SC_NM,
        address=" ".join(address_parts) or None,
    )


def parse_calorie(value: str | None) -> Calorie | None:
    if not value:
        return None
    match = _CALORIE.fullmatch(value)
    if not match:
        log_event(
            logger,
            logging.WARNING,
            "neis_optional_field_parse_failed",
            field="CAL_INFO",
        )
        return None
    return Calorie(amount=float(match.group(1)), unit="kcal")


def parse_nutrition(value: str | None) -> list[Nutrient]:
    nutrients = []
    for line in split_br(value):
        match = _NUTRIENT_WITH_UNIT.fullmatch(line)
        if match is None:
            match = _NUTRIENT_TRAILING_UNIT.fullmatch(line)
        if match is None:
            log_event(
                logger,
                logging.WARNING,
                "neis_optional_field_parse_failed",
                field="NTR_INFO",
            )
            continue
        nutrients.append(
            Nutrient(
                name=match.group("name").strip(),
                amount=float(match.group("amount")),
                unit=match.group("unit").strip(),
            )
        )
    return nutrients


def parse_origins(value: str | None) -> list[IngredientOrigin]:
    origins = []
    for line in split_br(value):
        ingredient, separator, origin = line.partition(":")
        if not separator or not ingredient.strip() or not origin.strip():
            log_event(
                logger,
                logging.WARNING,
                "neis_optional_field_parse_failed",
                field="ORPLC_INFO",
            )
            continue
        origins.append(
            IngredientOrigin(
                ingredient=ingredient.strip(),
                origin=origin.strip(),
            )
        )
    return origins


def map_meal(row: NeisMeal) -> Meal:
    try:
        meal_date = datetime.strptime(row.MLSV_YMD, "%Y%m%d").date()
    except ValueError as error:
        raise bad_neis_response() from error
    if row.MMEAL_SC_CODE != "2":
        raise bad_neis_response()
    return Meal(
        date=meal_date,
        dishes=split_br(row.DDISH_NM),
        calorie=parse_calorie(row.CAL_INFO),
        nutrition=parse_nutrition(row.NTR_INFO),
        origin_info=parse_origins(row.ORPLC_INFO),
        serving_count=row.MLSV_FGR,
    )
