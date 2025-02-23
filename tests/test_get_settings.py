# SPDX-FileCopyrightText: 2025 Justin Myers
#
# SPDX-License-Identifier: Unlicense

import os
import sys
from unittest import mock

import pytest

from adafruit_portalbase.network import NetworkBase


@pytest.fixture
def secrets():
    sys.modules["secrets.secrets"] = {
        "aio_key": "secret_aio_key",
        "aio_username": "secret_aio_username",
        "password": "secret_password",
        "ssid": "secret_ssid",
        "timezone": "secret_timezone",
        "fallback_test": "secret_fallback_test",
    }
    yield
    del sys.modules["secrets.secrets"]


@pytest.fixture
def settings_toml_current(monkeypatch):
    monkeypatch.setenv("ADAFRUIT_AIO_KEY", "settings_current_aio_key")
    monkeypatch.setenv("ADAFRUIT_AIO_USERNAME", "settings_current_aio_username")
    monkeypatch.setenv("CIRCUITPY_WIFI_PASSWORD", "settings_current_password")
    monkeypatch.setenv("CIRCUITPY_WIFI_SSID", "settings_current_ssid")
    monkeypatch.setenv("timezone", "settings_current_timezone")


@pytest.fixture
def settings_toml_old(monkeypatch):
    monkeypatch.setenv("AIO_KEY", "settings_old_aio_key")
    monkeypatch.setenv("AIO_USERNAME", "settings_old_aio_username")
    monkeypatch.setenv("CIRCUITPY_WIFI_PASSWORD", "settings_old_password")
    monkeypatch.setenv("CIRCUITPY_WIFI_SSID", "settings_old_ssid")
    monkeypatch.setenv("timezone", "settings_old_timezone")


def test_get_setting_does_not_exist():
    network = NetworkBase(None)
    assert network._get_setting("test") == None


@pytest.mark.parametrize(
    ("key", "value"),
    (
        ("ADAFRUIT_AIO_KEY", "secret_aio_key"),
        ("ADAFRUIT_AIO_USERNAME", "secret_aio_username"),
        ("AIO_KEY", "secret_aio_key"),
        ("AIO_USERNAME", "secret_aio_username"),
        ("CIRCUITPY_WIFI_PASSWORD", "secret_password"),
        ("CIRCUITPY_WIFI_SSID", "secret_ssid"),
        ("timezone", "secret_timezone"),
        ("not_found", None),
    ),
)
def test_get_setting_in_secrets(secrets, key, value):
    network = NetworkBase(None)
    with mock.patch("adafruit_portalbase.network.warnings.warn") as mock_warnings:
        assert network._get_setting(key) == value
    if value:
        mock_warnings.assert_called()


@pytest.mark.parametrize(
    ("key", "value"),
    (
        ("ADAFRUIT_AIO_KEY", "settings_current_aio_key"),
        ("ADAFRUIT_AIO_USERNAME", "settings_current_aio_username"),
        ("CIRCUITPY_WIFI_PASSWORD", "settings_current_password"),
        ("CIRCUITPY_WIFI_SSID", "settings_current_ssid"),
        ("timezone", "settings_current_timezone"),
        ("not_found", None),
    ),
)
def test_get_setting_in_settings_current(settings_toml_current, key, value):
    network = NetworkBase(None)
    with mock.patch("adafruit_portalbase.network.warnings.warn") as mock_warnings:
        assert network._get_setting(key) == value
    mock_warnings.assert_not_called()


@pytest.mark.parametrize(
    ("key", "value"),
    (
        ("ADAFRUIT_AIO_KEY", "settings_old_aio_key"),
        ("ADAFRUIT_AIO_USERNAME", "settings_old_aio_username"),
        ("CIRCUITPY_WIFI_PASSWORD", "settings_old_password"),
        ("CIRCUITPY_WIFI_SSID", "settings_old_ssid"),
        ("timezone", "settings_old_timezone"),
        ("not_found", None),
    ),
)
def test_get_setting_in_settings_old(settings_toml_old, key, value):
    network = NetworkBase(None)
    with mock.patch("adafruit_portalbase.network.warnings.warn") as mock_warnings:
        assert network._get_setting(key) == value
    mock_warnings.assert_not_called()
    if key in ["ADAFRUIT_AIO_KEY", "ADAFRUIT_AIO_USERNAME"]:
        assert os.getenv(key) is None


def test_fallback(secrets, settings_toml_current):
    network = NetworkBase(None)
    with mock.patch("adafruit_portalbase.network.warnings.warn") as mock_warnings:
        assert network._get_setting("ADAFRUIT_AIO_KEY") == "settings_current_aio_key"
    mock_warnings.assert_not_called()
    with mock.patch("adafruit_portalbase.network.warnings.warn") as mock_warnings:
        assert network._get_setting("fallback_test") == "secret_fallback_test"
    mock_warnings.assert_called()


def test_value_stored(settings_toml_current):
    network = NetworkBase(None)
    with mock.patch("os.getenv", return_value="test") as mock_getenv:
        assert network._get_setting("ADAFRUIT_AIO_KEY") == "test"
    mock_getenv.assert_called()
    with mock.patch("os.getenv", return_value="test") as mock_getenv:
        assert network._get_setting("ADAFRUIT_AIO_KEY") == "test"
    mock_getenv.assert_not_called()
