import socket

import pytest

import run


def test_runtime_options_use_corporate_network_defaults():
    assert run.runtime_options({}) == ("0.0.0.0", 8000, 8)


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "172.19.194.219"])
def test_runtime_options_reject_non_wildcard_listeners(host):
    with pytest.raises(ValueError, match="HOST debe ser 0.0.0.0"):
        run.runtime_options({"HOST": host})


def test_runtime_options_preserve_legacy_environment_names():
    assert run.runtime_options(
        {"WEB_HOST": "0.0.0.0", "WEB_PORT": "9000", "WEB_THREADS": "4"}
    ) == ("0.0.0.0", 9000, 4)


def test_local_ip_falls_back_to_hostname_addresses(monkeypatch):
    class UnavailableSocket:
        def connect(self, address):
            raise OSError("sin ruta")

        def close(self):
            pass

    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: UnavailableSocket())
    monkeypatch.setattr(socket, "gethostname", lambda: "servidor-corporativo")
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("172.19.194.219", 0)),
        ],
    )

    assert run.obtener_ip_local() == "172.19.194.219"
