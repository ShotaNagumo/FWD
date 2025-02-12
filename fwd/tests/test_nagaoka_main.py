import datetime
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
import nagaoka_datamodel
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


@pytest.fixture(scope="function")
def setup_db():
    # DB初期化
    FwdNagaoka.setup()

    # テスト実行
    yield

    # DB停止
    util_db_manager.ENGINE.dispose()

    # DB削除
    db_dir = Path("./variable_nagaoka")
    shutil.rmtree(db_dir)


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

    def test_xxx(self, setup_logger, setup_db):
        assert True

    def test_create_notify_text(self, mocker: MockFixture, setup_logger):
        instance = FwdNagaoka()

        # 入力値（発生系）
        input_data = nagaoka_datamodel.NagaokaDisasterDetail()
        input_data.raw_text_id = 1
        input_data.main_category = nagaoka_datamodel.DisasterMainCategory.火災
        input_data.sub_category = "建物火災"
        input_data.open_dt = datetime.datetime(2025, 1, 23, 1, 59)
        input_data.status = nagaoka_datamodel.DisasterStatus.発生
        input_data.address1 = ""
        input_data.address2 = "町名"
        input_data.address3 = "N丁目"
        input_data.close_dt = None

        # 期待値（発生系）
        expected_data = (
            "[長岡消防] 【火災】 町名 N丁目\n"
            "災害詳細：建物火災\n"
            "発生日時：2025/01/23 01:59"
        )

        # テスト（発生系）
        rendered_text = instance._create_notify_text(input_data)
        assert expected_data == rendered_text

        # 入力値（終了系）
        input_data.status = nagaoka_datamodel.DisasterStatus.鎮火
        input_data.close_dt = datetime.datetime(2025, 1, 23, 2, 59)

        # 期待値（終了系）
        expected_data = (
            "[長岡消防] 【鎮火】 町名 N丁目\n"
            "災害詳細：建物火災\n"
            "終了日時：2025/01/23 02:59 （発生日時：2025/01/23 01:59）"
        )

        # テスト（終了系）
        rendered_text = instance._create_notify_text(input_data)
        assert expected_data == rendered_text

        # 入力値（住所1, 2, 3）
        input_data.address1 = "市町村名"
        input_data.status = nagaoka_datamodel.DisasterStatus.発生
        input_data.close_dt = None

        # 期待値（住所1, 2, 3）
        expected_data = (
            "[長岡消防] 【火災】 市町村名 町名 N丁目\n"
            "災害詳細：建物火災\n"
            "発生日時：2025/01/23 01:59"
        )

        # テスト（住所1, 2, 3）
        rendered_text = instance._create_notify_text(input_data)
        assert expected_data == rendered_text

        # 入力値（住所1, 2）
        input_data.address3 = None

        # 期待値（住所1, 2）
        expected_data = (
            "[長岡消防] 【火災】 市町村名 町名\n"
            "災害詳細：建物火災\n"
            "発生日時：2025/01/23 01:59"
        )

        # テスト（住所1, 2）
        rendered_text = instance._create_notify_text(input_data)

        # 入力値（住所2）
        input_data.address1 = None

        # 期待値（住所2）
        expected_data = (
            "[長岡消防] 【火災】 町名\n災害詳細：建物火災\n発生日時：2025/01/23 01:59"
        )

        # テスト（住所2）
        rendered_text = instance._create_notify_text(input_data)

    def test_create_notify_text_exception(self, mocker: MockFixture, setup_logger):
        instance = FwdNagaoka()
        with mocker.patch("jinja2.environment.Template.render", side_effect=Exception):
            input_data = nagaoka_datamodel.NagaokaDisasterDetail()
            with pytest.raises(Exception):
                instance._create_notify_text(input_data)

    def test_create_data_for_create_notify_text(self, setup_logger):
        instance = FwdNagaoka()

        _open_dt = datetime.datetime.now()
        _close_dt = datetime.datetime.now()

        # 入力値
        input_data = nagaoka_datamodel.NagaokaDisasterDetail()
        input_data.raw_text_id = 1
        input_data.main_category = nagaoka_datamodel.DisasterMainCategory.火災
        input_data.sub_category = "建物火災"
        input_data.open_dt = _open_dt
        input_data.status = nagaoka_datamodel.DisasterStatus.発生
        input_data.address1 = None
        input_data.address2 = "町名"
        input_data.address3 = "N丁目"
        input_data.close_dt = None

        # 期待値
        expected_data = {
            "main_category": "火災",
            "sub_category": "建物火災",
            "open_dt": _open_dt.strftime(r"%Y/%m/%d %H:%M"),
            "status": "発生",
            "address1": None,
            "address2": "町名",
            "address3": "N丁目",
            "close_dt": "",
        }

        # テスト（close_dt有の場合）
        output_data = instance._create_data_for_create_notify_text(input_data)
        assert expected_data == output_data

        # 入力値・期待値にclose_dtを追加
        input_data.close_dt = _close_dt
        expected_data["close_dt"] = _close_dt.strftime(r"%Y/%m/%d %H:%M")

        # テスト（close_dt無の場合）
        output_data = instance._create_data_for_create_notify_text(input_data)
        assert expected_data == output_data
