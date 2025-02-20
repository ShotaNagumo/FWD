import argparse
import logging
import shutil
import sys
from pathlib import Path

import pytest
import yaml
from pytest_mock import MockFixture

src_path = Path(__file__).parents[1] / "src"
sys.path.append(src_path.as_posix())

import fwd_launcher
import util_config


@pytest.fixture(scope="session")
def logger_setup():
    # ログファイル設定パスを上書き
    log_format_file_path = (
        Path(__file__).parents[1]
        / "tests_resource"
        / "test_util_logger_initializer_1.yaml"
    )
    fwd_launcher.LOG_FORMAT_FILE_PATH = log_format_file_path

    # テスト実行
    yield

    # ログ出力ディレクトリの削除
    logging.shutdown()
    log_setting_data = yaml.safe_load(log_format_file_path.read_text(encoding="utf-8"))
    handlers = log_setting_data.get("handlers")
    for handler_name in handlers.keys():
        if file_name := handlers[handler_name].get("filename", None):
            log_out_dir = Path(file_name).parent
            if log_out_dir.exists():
                shutil.rmtree(log_out_dir)


class TestFwdLauncher:
    def test_create_argparser(self):
        parser = fwd_launcher._create_argparser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_setup_fwd(self, mocker: MockFixture, logger_setup):
        # 設定データをテスト用に上書き
        setting_data = {
            "variable_dir": "./variable_launcher",
            "nagaoka": {
                "webhook_url": "https://discordapp.com/api/webhooks/0123456789/abcdefghijklmnopqrstuvwxyz"
            },
        }
        util_config.SETTING_DATA = setting_data

        # テスト対象関数呼び出し
        fwd_launcher.setup_fwd(argparse.Namespace())

        # テストで作成した一時ディレクトリを削除する（Variableディレクトリ）
        # DBパスはインポート時に決定されるため、本テストファイルの先頭でインポートすると
        # 本テストで変更したDBパスが反映されなくなってしまう。
        # そこで、ここでインポートを行う。
        import util_db_manager

        util_db_manager.ENGINE.dispose()
        variable_dir = Path(setting_data["variable_dir"])
        if variable_dir.exists():
            shutil.rmtree(variable_dir)

    def test_execute_nagaoka(self, mocker: MockFixture, logger_setup):
        # テスト対象関数を呼び出し
        with mocker.patch("nagaoka_main.FwdNagaoka.execute", return_value=True):
            fwd_launcher.execute_nagaoka(argparse.Namespace())

    def test_store_old_nagaoka(self, mocker: MockFixture, logger_setup):
        # テスト対象関数を呼び出し
        with mocker.patch("nagaoka_main.FwdNagaoka.store_old_data", return_value=True):
            fwd_launcher.store_old_nagaoka(argparse.Namespace(text_dir="dummy"))

    def test_create_config_file(self, mocker: MockFixture):
        # config出力ディレクトリを上書き
        _config_path_backup = fwd_launcher.CONFIG_FILE_PATH
        fwd_launcher.CONFIG_FILE_PATH = (
            Path(__file__).parents[1] / "variable_config" / "fwd_config_test.yaml"
        )

        # log_format出力ディレクトリを上書き
        _log_format_path_backup = fwd_launcher.LOG_FORMAT_FILE_PATH
        fwd_launcher.LOG_FORMAT_FILE_PATH = (
            Path(__file__).parents[1] / "variable_config" / "fwd_log_format_test.yaml"
        )

        # config正解データ読み込み
        config_expect_file_path = (
            Path(__file__).parents[1] / "tests_resource" / "fwd_config_expect.yaml"
        )
        config_expect_data = config_expect_file_path.read_text(encoding="utf-8")

        # log_format正解データ読み込み
        log_format_expect_file_path = (
            Path(__file__).parents[1] / "tests_resource" / "fwd_log_format_expect.yaml"
        )
        log_format_expect_data = log_format_expect_file_path.read_text(encoding="utf-8")

        try:
            # config出力ディレクトリを作成
            fwd_launcher.CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

            # log_format出力ディレクトリを作成
            fwd_launcher.LOG_FORMAT_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

            # テスト対象関数実行
            effects = [
                "D:/work/fwd/variable",
                "https://discordapp.com/api/webhooks/0123456789/abcdefghijklmnopqrstuvwxyz",
            ]
            with mocker.patch("builtins.input", side_effect=effects):
                fwd_launcher.create_config_file(argparse.Namespace())

            # configテスト結果確認
            assert config_expect_data == fwd_launcher.CONFIG_FILE_PATH.read_text(
                encoding="utf-8"
            )

            # log_formatテスト結果確認
            assert (
                log_format_expect_data
                == fwd_launcher.LOG_FORMAT_FILE_PATH.read_text(encoding="utf-8")
            )

        finally:
            # 作業ディレクトリを削除
            if fwd_launcher.CONFIG_FILE_PATH.parent.is_dir():
                shutil.rmtree(fwd_launcher.CONFIG_FILE_PATH.parent)
            if fwd_launcher.LOG_FORMAT_FILE_PATH.parent.is_dir():
                shutil.rmtree(fwd_launcher.LOG_FORMAT_FILE_PATH.parent)

            # config, log_formatファイルパスの設定を元に戻す
            fwd_launcher.CONFIG_FILE_PATH = _config_path_backup
            fwd_launcher.LOG_FORMAT_FILE_PATH = _log_format_path_backup
