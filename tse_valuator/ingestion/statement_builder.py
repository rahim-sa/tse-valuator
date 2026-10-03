"""
Assembles a NormalizedStatement from a raw Codal 'Excel' export.

This is the seam between raw parsing (statement_parser, label_mapper,
value_parser — all pure, deterministic code) and the validated schema
everything downstream depends on. No LLM involvement here; unmapped
labels are collected and returned separately for human/LLM review
later, never silently dropped or guessed.
"""

from __future__ import annotations
from dataclasses import dataclass 
from datetime import datetime, timezone

from tse_valuator.ingestion.label_mapper import try_map_label
from tse_valuator.ingestion.schema import (
    ConsolidationBasis,
    ExtractionFlag,
    LineItem,
    NormalizedStatement,
    SourceCitation,
    StatementType,
)
from tse_valuator.ingestion.statement_parser import parse_codal_excel_export
from tse_valuator.ingestion.value_parser import UnparsableValueError, parse_codal_number


@dataclass
class BuildResult:
    statement: NormalizedStatement | None
    unmapped_labels: list[str]
    unparsable_values: list[tuple[str, str]]  # (label, raw_value)


def build_normalized_statement(
    html_bytes: bytes,
    filing_url: str,
    symbol_fa: str,
    company_name_fa: str,
    statement_type: StatementType,
    consolidation_basis: ConsolidationBasis,
    period,  # FiscalPeriod — imported by caller to avoid circular concerns here
    extractor_model: str = "static-lookup-v1",
) -> BuildResult:
    sections = parse_codal_excel_export(html_bytes)

    line_items: list[LineItem] = []
    unmapped_labels: list[str] = []
    unparsable_values: list[tuple[str, str]] = []

    #now = datetime.utcnow()
    now = datetime.now(timezone.utc)

    for section in sections:
        for label, values in section.rows.items():
            key = try_map_label(label)
            if key is None:
                unmapped_labels.append(label)
                continue

            raw_value = values[0] if values else ""
            try:
                parsed = parse_codal_number(raw_value)
            except UnparsableValueError:
                unparsable_values.append((label, raw_value))
                continue

            flag = ExtractionFlag.OK if parsed is not None else ExtractionFlag.MISSING_IN_FILING

            line_items.append(
                LineItem(
                    key=key,
                    value_rial=parsed,
                    citation=SourceCitation(
                        filing_url=filing_url,
                        raw_label_fa=label,
                        extractor_model=extractor_model,
                        extracted_at=now,
                    ),
                    flag=flag,
                )
            )

    if not line_items:
        return BuildResult(statement=None, unmapped_labels=unmapped_labels, unparsable_values=unparsable_values)

    statement = NormalizedStatement(
        symbol_fa=symbol_fa,
        company_name_fa=company_name_fa,
        statement_type=statement_type,
        consolidation_basis=consolidation_basis,
        period=period,
        line_items=line_items,
    )

    return BuildResult(statement=statement, unmapped_labels=unmapped_labels, unparsable_values=unparsable_values)