import argparse
import logging
import shutil
import sys
from pathlib import Path

import yaml
from pytest_mock import MockFixture

src_path = Path(__file__).parents[1] / "src"
sys.path.append(src_path.as_posix())

import fwd_launcher
import util_config


class TestFwdLauncher:
    def test_create_argparser(self):
        parser = fwd_launcher._create_argparser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_setup_fwd(self, mocker: MockFixture):
        # 設定データをテスト用に上書き
        setting_data = {
            "variable_dir": "./variable_launcher",
            "nagaoka": {
                "webhook_url": "https://discordapp.com/api/webhooks/0123456789/abcdefghijklmnopqrstuvwxyz"
            },
        }
        util_config.SETTING_DATA = setting_data

        # ログファイル設定パスを上書き
        log_format_file_path = (
            Path(__file__).parents[1]
            / "tests_resource"
            / "test_util_logger_initializer_1.yaml"
        )
        fwd_launcher.LOG_FORMAT_FILE_PATH = log_format_file_path

        # テスト対象関数呼び出し
        fwd_launcher.setup_fwd(argparse.Namespace())

        # テストで作成した一時ディレクトリを削除する（Variableディレクトリ）
        # DBパスはインポート時に決定されるため、本テストファイルの先頭でインポートすると
        # 本テストで変更したDBパスが反映されなくなってしまう。
        # そこで、ここでインポートを行う。
        import util_db_manager

        util_db_manager.ENGINE.dispose()  # DBを閉じ、下の削除処理でエラーとなることを防ぐ。
        variable_dir = Path(setting_data["variable_dir"])
        if variable_dir.exists():
            shutil.rmtree(variable_dir)

        # テストで作成した一時ディレクトリを削除する（ログディレクトリ）
        logging.shutdown()
        log_setting_data = yaml.safe_load(
            log_format_file_path.read_text(encoding="utf-8")
        )
        handlers = log_setting_data.get("handlers")
        for handler_name in handlers.keys():
            if file_name := handlers[handler_name].get("filename", None):
                log_out_dir = Path(file_name).parent
                if log_out_dir.exists():
                    shutil.rmtree(log_out_dir)
