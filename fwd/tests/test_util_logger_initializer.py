import logging
import shutil
from pathlib import Path

import pytest
import yaml
from pytest_mock import MockFixture

from fwd.src.util_logger_initializer import initialize


class TestUtilLoggerInitializer:
    def test_util_logger_initializer(self):
        # 設定ファイルパス
        setting_file_path = (
            Path(__file__).parents[1]
            / "tests_resource"
            / "test_util_logger_initializer_1.yaml"
        )

        # テスト対象関数呼び出し
        initialize(setting_file_path)

        # 設定ファイルから設定内容を読み出しておく
        setting_data = yaml.safe_load(setting_file_path.read_text(encoding="utf-8"))
        handlers = setting_data.get("handlers")

        # 各handlerに応じたログファイルが作成されていればOKと判定する
        for handler_name in handlers.keys():
            if file_name := handlers[handler_name].get("filename", None):
                assert Path(file_name).exists()

        # ログ設定を削除する
        logging.shutdown()

        # テストで作成した一時ディレクトリを削除する
        for handler_name in handlers.keys():
            if file_name := handlers[handler_name].get("filename", None):
                log_out_dir = Path(file_name).parent
                if log_out_dir.exists():
                    shutil.rmtree(log_out_dir)

    def test_util_logger_initializer_exception(self, mocker: MockFixture):
        # 設定ファイルパス
        setting_file_path = (
            Path(__file__).parents[1]
            / "tests_resource"
            / "test_util_logger_initializer_1.yaml"
        )

        # テスト対象関数呼び出し
        mocker.patch("yaml.safe_load", side_effect=Exception)
        with pytest.raises(Exception):
            initialize(setting_file_path)

        # ログ設定を削除する
        logging.shutdown()
