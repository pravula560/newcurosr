from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ExtractSqlParams:
    product_lines: tuple[str, ...]
    created_start: date
    created_end: date | None = None
    eligible_only: bool = False


def _quote_string_literal(value: str) -> str:
    # BigQuery string literal quoting. Prevents accidental quote breaks when templating.
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _render_product_line_in(product_lines: Iterable[str]) -> str:
    values: list[str] = []
    for pl in product_lines:
        pl_norm = pl.strip().upper()
        if not pl_norm:
            continue
        values.append(_quote_string_literal(pl_norm))
    if not values:
        raise ValueError("product_lines must contain at least one non-empty value")
    return ", ".join(values)


def render_extract_sql(template_sql: str, params: ExtractSqlParams) -> str:
    created_end_sql = ""
    if params.created_end is not None:
        created_end_sql = f"    AND DATE(A.created_datetime) < '{params.created_end.isoformat()}'"

    flag_eligible_sql = ""
    if params.eligible_only:
        flag_eligible_sql = "    AND A.flag_eligible_lead = TRUE"

    replacements = {
        "__PRODUCT_LINE_IN__": _render_product_line_in(params.product_lines),
        "__CREATED_START__": params.created_start.isoformat(),
        "__CREATED_END_SQL__": created_end_sql,
        "__FLAG_ELIGIBLE_SQL__": flag_eligible_sql,
    }

    rendered = template_sql
    for k, v in replacements.items():
        rendered = rendered.replace(k, v)

    missing = [k for k in replacements if k in rendered]
    # If a placeholder still exists, it means template changed or param renderer failed.
    if missing:
        raise ValueError(f"SQL template still contains placeholders after rendering: {missing}")

    return rendered


def load_sql_template(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")
