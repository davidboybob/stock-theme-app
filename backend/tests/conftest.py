"""pytest 설정"""
import pytest

# pytest-asyncio 자동 모드 설정
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
