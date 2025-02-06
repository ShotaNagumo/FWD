import logging
import shutil
import sys
from pathlib import Path

import pytest
import yaml
from pytest_mock import MockFixture

from fwd.src.util_logger_initializer import initialize

src_path = Path(__file__).parents[1] / "src"
sys.path.append(src_path.as_posix())

import util_config
from nagaoka_main import FwdNagaoka


@pytest.fixture(scope="class")
def setup_setting():
    # 設定内容を更新
    setting_data = {
        "variable_dir": "./variable",
        "nagaoka": {
            "webhook_url": "https://discord.com/api/webhooks/0123456789/abcdefghijklmnopqrstuvwxyz",
        },
    }
    util_config.SETTING_DATA = setting_data

    # 設定ファイルパス
    setting_file_path = (
        Path(__file__).parents[1]
        / "tests_resource"
        / "test_util_logger_initializer_1.yaml"
    )

    # logger初期化
    initialize(setting_file_path)

    # テスト実行
    yield

    # テスト実行後、ログ設定を削除する
    logging.shutdown()

    # ログファイルを削除する
    setting_data = yaml.safe_load(setting_file_path.read_text(encoding="utf-8"))
    handlers = setting_data.get("handlers")
    for handler_name in handlers.keys():
        if file_name := handlers[handler_name].get("filename", None):
            log_out_dir = Path(file_name).parent
            if log_out_dir.exists():
                shutil.rmtree(log_out_dir)


class TestNagaokaMain:
    def test_cleansing_webtext(self, mocker: MockFixture, setup_setting):
        instance = FwdNagaoka()
        input_text = (
            "12月23日　01:23　長岡市 町名 ２丁目に建物火災のため消防車が出動しました。"
        )
        expected_text = (
            "12月23日 01:23 長岡市 町名 ２丁目に建物火災のため消防車が出動しました。"
        )
        output_text = instance._cleansing_webtext(input_text)
        assert expected_text == output_text
