from pathlib import Path

import pytest
from pytest_mock import MockFixture

import fwd.src.util_config


class TestUtilConfig:
    def test_get_config_dir(self):
        expect_dir = Path(__file__).parents[1] / "config"
        config_dir = fwd.src.util_config.get_config_dir()
        assert expect_dir == config_dir

    def test_resource_dir(self):
        expect_dir = Path(__file__).parents[1] / "resource"
        resource_dir = fwd.src.util_config.get_resource_dir()
        assert expect_dir == resource_dir

    def test_get_variable_dir(self, mocker: MockFixture):
        # テスト用の設定データを用意
        fwd.src.util_config.SETTING_DATA = None
        dummy_data = {"variable_dir": "./variable"}
        mocker.patch("yaml.safe_load", return_value=dummy_data)

        # テスト実行
        variable_dir = fwd.src.util_config.get_variable_dir()
        assert Path("./variable") == variable_dir

    def test_get_variable_dir_not_defined(self, mocker: MockFixture):
        # テスト用の設定データを用意
        fwd.src.util_config.SETTING_DATA = None
        mocker.patch("yaml.safe_load", return_value={})

        # テスト実行
        with pytest.raises(ValueError):
            _ = fwd.src.util_config.get_variable_dir()

    def test_get_webhook_url(self, mocker: MockFixture):
        # テスト用の設定データを用意
        fwd.src.util_config.SETTING_DATA = None
        dummy_data = {
            "nagaoka": {
                "webhook_url": "https://discord.com/api/webhooks/0123456789",
            }
        }
        mocker.patch("yaml.safe_load", return_value=dummy_data)

        # テスト実行
        webhook_url = fwd.src.util_config.get_webhook_url("nagaoka")
        assert "https://discord.com/api/webhooks/0123456789" == webhook_url

    def test_get_webhook_url_not_defined_city(self, mocker: MockFixture):
        # テスト用の設定データを用意
        fwd.src.util_config.SETTING_DATA = None
        mocker.patch("yaml.safe_load", return_value={})

        # テスト実行
        with pytest.raises(ValueError):
            _ = fwd.src.util_config.get_webhook_url("nagaoka")

    def test_get_webhook_url_not_defined_url(self, mocker: MockFixture):
        # テスト用の設定データを用意
        fwd.src.util_config.SETTING_DATA = None
        dummy_data = {"nagaoka": {}}
        mocker.patch("yaml.safe_load", return_value=dummy_data)

        # テスト実行
        with pytest.raises(ValueError):
            _ = fwd.src.util_config.get_webhook_url("nagaoka")
