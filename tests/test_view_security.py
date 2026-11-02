from types import SimpleNamespace

from django.test import override_settings

from portal.views import _client_ip, _csv_safe


def request(**meta):
    return SimpleNamespace(META=meta)


def test_forwarded_ip_is_ignored_without_trusted_proxy():
    value = _client_ip(
        request(HTTP_X_FORWARDED_FOR="203.0.113.10", REMOTE_ADDR="10.0.0.7")
    )

    assert value == "10.0.0.7"


@override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
def test_forwarded_ip_is_used_when_proxy_is_trusted():
    value = _client_ip(
        request(
            HTTP_X_FORWARDED_FOR="203.0.113.10, 10.0.0.7",
            REMOTE_ADDR="10.0.0.7",
        )
    )

    assert value == "203.0.113.10"


def test_csv_export_neutralizes_spreadsheet_formulas():
    assert _csv_safe("=HYPERLINK(\"https://example.invalid\")").startswith("'")
    assert _csv_safe("PORTABILIDAD") == "PORTABILIDAD"
