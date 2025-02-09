import logging
import shutil
import sys
from pathlib import Path

import pytest
import yaml
from pytest_mock import MockFixture

src_path = Path(__file__).parents[1] / "src"
sys.path.append(src_path.as_posix())

import util_config

# 設定内容を更新（FwdNagaokaをインポートする前に実行する必要がある）
setting_data = {
    "variable_dir": "./variable_nagaoka",
    "nagaoka": {
        "webhook_url": "https://discord.com/api/webhooks/0123456789/abcdefghijklmnopqrstuvwxyz",
    },
}
util_config.SETTING_DATA = setting_data

# 自作モジュールの読み込み（設定データ更新後にインポートする）
import util_db_manager
import util_logger_initializer
from nagaoka_main import FwdNagaoka

TEST_RESOURCE_DIR = Path(__file__).parents[1] / "tests_resource"


@pytest.fixture(scope="class")
def setup_logger():
    # ログフォーマットファイルパス
    setting_file_path = TEST_RESOURCE_DIR / "test_util_logger_initializer_1.yaml"

    # logger初期化
    util_logger_initializer.initialize(setting_file_path)

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
    def test_cleansing_webtext(self, mocker: MockFixture, setup_logger):
        instance = FwdNagaoka()
        input_text = (
            "12月23日　01:23　長岡市 町名 ２丁目に建物火災のため消防車が出動しました。"
        )
        expected_text = (
            "12月23日 01:23 長岡市 町名 ２丁目に建物火災のため消防車が出動しました。"
        )
        output_text = instance._cleansing_webtext(input_text)
        assert expected_text == output_text

    def test_split_webtext(self, setup_logger):
        instance = FwdNagaoka()

        # テスト入力ファイル
        input_path = TEST_RESOURCE_DIR / "nagaoka_webtext_1.txt"
        input_data = instance._cleansing_webtext(input_path.read_text(encoding="utf-8"))

        # 期待値データファイルを読み込み
        expected_curr_path = TEST_RESOURCE_DIR / "nagaoka_webtext_1_expected_curr.txt"
        expected_curr_data = expected_curr_path.read_text(encoding="utf-8")
        expected_past_path = TEST_RESOURCE_DIR / "nagaoka_webtext_1_expected_past.txt"
        expected_past_data = expected_past_path.read_text(encoding="utf-8")

        # テスト対象関数を実行
        output_curr, output_past = instance._split_webtext(input_data)

        # テスト結果を評価
        assert expected_curr_data == output_curr
        assert expected_past_data == output_past

    def test_split_webtext_exception(self, setup_logger):
        instance = FwdNagaoka()
        with pytest.raises(ValueError):
            instance._split_webtext("dummy")

    def test_get_close_dt(self, setup_logger):
        pass
