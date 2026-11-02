from datetime import date
from decimal import Decimal

from validaciones.management.commands.inspeccionar_oracle import (
    CAMPAIGN_COUNT_SQL,
    METADATA_QUERIES,
    _json_value,
)


def test_metadata_queries_are_read_only_selects():
    statements = [*METADATA_QUERIES.values(), CAMPAIGN_COUNT_SQL]
    forbidden = ("INSERT ", "UPDATE ", "DELETE ", "MERGE ", "CREATE ", "ALTER ", "DROP ", "TRUNCATE ")

    for statement in statements:
        normalized = " ".join(statement.upper().split())
        assert normalized.startswith("SELECT ")
        assert not any(keyword in normalized for keyword in forbidden)


def test_json_value_serializes_oracle_friendly_types():
    assert _json_value(Decimal("0.30")) == "0.30"
    assert _json_value(date(2026, 10, 24)) == "2026-10-24"
    assert _json_value("A") == "A"
