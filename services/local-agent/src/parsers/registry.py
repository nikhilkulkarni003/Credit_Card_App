"""Parser registry — maps bank_code -> StatementParser implementation."""

from __future__ import annotations

from src.parsers.base import StatementParser
from src.parsers.hdfc import HdfcStatementParser
from src.parsers.icici import IciciStatementParser

_REGISTRY: dict[str, type[StatementParser]] = {
    "HDFC": HdfcStatementParser,
    "ICICI": IciciStatementParser,
}


def get_parser(bank_code: str) -> StatementParser:
    parser_cls = _REGISTRY.get(bank_code.upper())
    if parser_cls is None:
        raise KeyError(f"No parser registered for bank_code={bank_code!r}")
    return parser_cls()


def register_parser(bank_code: str, parser_cls: type[StatementParser]) -> None:
    _REGISTRY[bank_code.upper()] = parser_cls
