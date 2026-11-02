from types import SimpleNamespace

from validaciones.management.commands.verificar_oracle import friendly_oracle_error


def test_unknown_oracle_error_keeps_safe_code_and_message():
    detail = SimpleNamespace(
        code=30556,
        message="ORA-30556: either functional or bitmap join index is defined",
    )
    error = SimpleNamespace(args=[detail])

    assert friendly_oracle_error(error) == (
        "Oracle devolvió ORA-30556: "
        "either functional or bitmap join index is defined"
    )
