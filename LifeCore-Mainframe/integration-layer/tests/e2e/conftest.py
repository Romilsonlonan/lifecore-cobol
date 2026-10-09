"""
conftest.py — Playwright
Inicia o servidor uvicorn em background antes dos testes E2E
e encerra após a sessão.
"""

import socket
import subprocess
import time

import pytest


def _porta_livre(host: str, porta: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, porta)) != 0


@pytest.fixture(scope="session", autouse=True)
def servidor_fastapi():
    """
    Sobe o uvicorn na porta 8000 antes da suite E2E.
    Encerra o processo ao final da sessão.
    """
    if not _porta_livre("localhost", 8000):
        # Servidor já está rodando (dev manual) — não sobe outro
        yield
        return

    proc = subprocess.Popen(
        [
            "python",
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Aguarda o servidor aceitar conexões (máx 10s)
    for _ in range(20):
        if not _porta_libre("localhost", 8000):
            break
        time.sleep(0.5)

    yield proc

    proc.terminate()
    proc.wait(timeout=5)


def _porta_libre(host: str, porta: int) -> bool:
    """Alias para legibilidade nos loops de espera."""
    return _porta_livre(host, porta)
