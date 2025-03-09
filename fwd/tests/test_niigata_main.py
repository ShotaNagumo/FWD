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

# 設定内容を更新（FwdNiigataをインポートする前に実行する必要がある）
setting_data = {
    "variable_dir": "./variable_niigata",
    "niigata": {
        "webhook_url": "https://discord.com/api/webhooks/0123456789/abcdefghijklmnopqrstuvwxyz",
    },
}
util_config.SETTING_DATA = setting_data

# 自作モジュールの読み込み（設定データ更新後にインポートする）
import util_db_manager
import util_logger_initializer
from niigata_datamodel import NiigataNoticeText, NoticeType, NotifyStatus
from niigata_main import FwdNiigata

TEST_RESOURCE_DIR = Path(__file__).parents[1] / "tests_resource"


@pytest.fixture(scope="session")
def setup_logger():
    # ログフォーマットファイルパス
    setting_file_path = TEST_RESOURCE_DIR / "test_util_logger_initializer_2.yaml"

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


@pytest.fixture(scope="session")
def setup_db():
    # DB初期化
    FwdNiigata.setup()

    # テスト実行
    yield

    # DB停止
    util_db_manager.ENGINE.dispose()

    # DB削除
    db_dir = Path("./variable_niigata")
    shutil.rmtree(db_dir)


class TestNiigataMain:
    def test_split_webtext_topInformationなし(self, setup_logger):
        instance = FwdNiigata()

        # テスト入力ファイル
        input_path = TEST_RESOURCE_DIR / "niigata_webtext_1.txt"
        input_data = input_path.read_text(encoding="utf-8")

        # テスト対象関数実行
        output_top, output_newinfo = instance._split_webtext(input_data)

        # 期待値データファイルを読み込み
        expected_newinfo_path = (
            TEST_RESOURCE_DIR / "niigata_webtext_1_expected_newinfo.txt"
        )
        expected_newinfo_data = expected_newinfo_path.read_text(encoding="utf-8")

        # 評価
        assert output_top == ""
        assert output_newinfo == expected_newinfo_data

    def test_split_webtext_topInformationあり(self, setup_logger):
        instance = FwdNiigata()

        # テスト入力ファイル
        input_path = TEST_RESOURCE_DIR / "niigata_webtext_2.txt"
        input_data = input_path.read_text(encoding="utf-8")

        # テスト対象関数実行
        output_topinfo, output_newinfo = instance._split_webtext(input_data)

        # 期待値データファイルを読み込み
        expected_topinfo_path = (
            TEST_RESOURCE_DIR / "niigata_webtext_2_expected_topinfo.txt"
        )
        expected_newinfo_path = (
            TEST_RESOURCE_DIR / "niigata_webtext_2_expected_newinfo.txt"
        )
        expected_newinfo_data = expected_newinfo_path.read_text(encoding="utf-8")
        expected_topinfo_data = expected_topinfo_path.read_text(encoding="utf-8")

        # 評価
        assert output_topinfo == expected_topinfo_data
        assert output_newinfo == expected_newinfo_data

    def test_split_webtext_exception(self, setup_logger):
        instance = FwdNiigata()
        with pytest.raises(ValueError):
            instance._split_webtext("dummy")

    def test_commit_disaster_list_notice(self, setup_logger, setup_db):
        session = util_db_manager.SESSION()
        try:
            # インスタンス作成
            instance = FwdNiigata()

            # テストデータ読み込み
            input_file_path = (
                TEST_RESOURCE_DIR / "niigata_webtext_2_expected_topinfo.txt"
            )
            webpage_text_curr = input_file_path.read_text(encoding="utf-8")

            # 案内情報を登録できること
            instance._commit_disaster_list_notice(webpage_text_curr)
            results = session.query(NiigataNoticeText).all()
            assert len(results) == 1
            assert results[0].notice_type == NoticeType.一般案内
            assert (
                results[0].raw_text
                == "令和6年能登半島地震に伴い、新潟市消防局の部隊が緊急消防援助隊として、石川県へ出動しております。"
            )
            assert results[0].notify_status == NotifyStatus.NOT_YET

            # 同一内容を登録しないこと
            instance._commit_disaster_list_notice(webpage_text_curr)
            results = session.query(NiigataNoticeText).all()
            assert len(results) == 1

        finally:
            # テスト結果として保存されたデータを削除
            session.query(NiigataNoticeText).delete()
            session.commit()

    def test_commit_disaster_list_notice_情報無し(self, setup_logger, setup_db):
        session = util_db_manager.SESSION()
        try:
            # インスタンス作成
            instance = FwdNiigata()

            # 案内情報無しの場合登録されないこと
            instance._commit_disaster_list_notice("")
            results = session.query(NiigataNoticeText).all()
            assert len(results) == 0

        finally:
            # テスト結果として保存されたデータを削除
            session.query(NiigataNoticeText).delete()
            session.commit()

    def test_commit_disaster_list_notice_dt指定(self, setup_logger, setup_db):
        session = util_db_manager.SESSION()
        try:
            # インスタンス作成
            instance = FwdNiigata()

            # dtを指定して案内情報を登録できること
            dt = datetime.datetime(2025, 1, 2, 12, 34)
            instance._commit_disaster_list_notice("案内情報", dt)
            results = session.query(NiigataNoticeText).all()
            assert len(results) == 1
            assert results[0].retr_dt == dt

        finally:
            # テスト結果として保存されたデータを削除
            session.query(NiigataNoticeText).delete()
            session.commit()

    def test_commit_disaster_list_notice_exception(
        self, mocker: MockFixture, setup_logger, setup_db
    ):
        # インスタンス作成
        instance = FwdNiigata()

        # 例外発生すること
        with (
            mocker.patch("sqlalchemy.orm.Session.query", side_effect=Exception),
            pytest.raises(Exception),
        ):
            instance._commit_disaster_list_notice("案内情報")

    @pytest.mark.skip
    def test_create_testfile(self, setup_logger, setup_db):
        import unicodedata

        instance = FwdNiigata()
        i_path = TEST_RESOURCE_DIR / "20220117_1714.txt"
        o_path = i_path.with_name("niigata_webtext_6_newinfo.txt")

        i_data = i_path.read_text(encoding="utf-8")
        i_data = unicodedata.normalize("NFKC", i_data)
        _, o_data = instance._split_webtext(i_data)
        o_path.write_text(o_data, encoding="utf-8")

    # def test_create_notify_text(self, mocker: MockFixture, setup_logger):
    #     instance = FwdNiigata()

    #     # 入力値（発生系）
    #     input_data = niigata_datamodel.niigataDisasterDetail()
    #     input_data.raw_text_id = 1
    #     input_data.main_category = niigata_datamodel.DisasterMainCategory.火災
    #     input_data.sub_category = "建物火災"
    #     input_data.open_dt = datetime.datetime(2025, 1, 23, 1, 59)
    #     input_data.status = niigata_datamodel.DisasterStatus.発生
    #     input_data.address1 = ""
    #     input_data.address2 = "町名"
    #     input_data.address3 = "N丁目"
    #     input_data.close_dt = None

    #     # 期待値（発生系）
    #     expected_data = (
    #         "[長岡消防] 【火災】 町名 N丁目\n"
    #         "災害詳細：建物火災\n"
    #         "発生日時：2025/01/23 01:59"
    #     )

    #     # テスト（発生系）
    #     rendered_text = instance._create_notify_text(input_data)
    #     assert expected_data == rendered_text

    #     # 入力値（終了系）
    #     input_data.status = niigata_datamodel.DisasterStatus.鎮火
    #     input_data.close_dt = datetime.datetime(2025, 1, 23, 2, 59)

    #     # 期待値（終了系）
    #     expected_data = (
    #         "[長岡消防] 【鎮火】 町名 N丁目\n"
    #         "災害詳細：建物火災\n"
    #         "終了日時：2025/01/23 02:59 （発生日時：2025/01/23 01:59）"
    #     )

    #     # テスト（終了系）
    #     rendered_text = instance._create_notify_text(input_data)
    #     assert expected_data == rendered_text

    #     # 入力値（住所1, 2, 3）
    #     input_data.address1 = "市町村名"
    #     input_data.status = niigata_datamodel.DisasterStatus.発生
    #     input_data.close_dt = None

    #     # 期待値（住所1, 2, 3）
    #     expected_data = (
    #         "[長岡消防] 【火災】 市町村名 町名 N丁目\n"
    #         "災害詳細：建物火災\n"
    #         "発生日時：2025/01/23 01:59"
    #     )

    #     # テスト（住所1, 2, 3）
    #     rendered_text = instance._create_notify_text(input_data)
    #     assert expected_data == rendered_text

    #     # 入力値（住所1, 2）
    #     input_data.address3 = None

    #     # 期待値（住所1, 2）
    #     expected_data = (
    #         "[長岡消防] 【火災】 市町村名 町名\n"
    #         "災害詳細：建物火災\n"
    #         "発生日時：2025/01/23 01:59"
    #     )

    #     # テスト（住所1, 2）
    #     rendered_text = instance._create_notify_text(input_data)

    #     # 入力値（住所2）
    #     input_data.address1 = None

    #     # 期待値（住所2）
    #     expected_data = (
    #         "[長岡消防] 【火災】 町名\n災害詳細：建物火災\n発生日時：2025/01/23 01:59"
    #     )

    #     # テスト（住所2）
    #     rendered_text = instance._create_notify_text(input_data)

    # def test_create_notify_text_exception(self, mocker: MockFixture, setup_logger):
    #     instance = FwdNiigata()
    #     with mocker.patch("jinja2.environment.Template.render", side_effect=Exception):
    #         input_data = niigata_datamodel.niigataDisasterDetail()
    #         with pytest.raises(Exception):
    #             instance._create_notify_text(input_data)

    # def test_create_data_for_create_notify_text(self, setup_logger):
    #     instance = FwdNiigata()

    #     _open_dt = datetime.datetime.now()
    #     _close_dt = datetime.datetime.now()

    #     # 入力値
    #     input_data = niigata_datamodel.niigataDisasterDetail()
    #     input_data.raw_text_id = 1
    #     input_data.main_category = niigata_datamodel.DisasterMainCategory.火災
    #     input_data.sub_category = "建物火災"
    #     input_data.open_dt = _open_dt
    #     input_data.status = niigata_datamodel.DisasterStatus.発生
    #     input_data.address1 = None
    #     input_data.address2 = "町名"
    #     input_data.address3 = "N丁目"
    #     input_data.close_dt = None

    #     # 期待値
    #     expected_data = {
    #         "main_category": "火災",
    #         "sub_category": "建物火災",
    #         "open_dt": _open_dt.strftime(r"%Y/%m/%d %H:%M"),
    #         "status": "発生",
    #         "address1": None,
    #         "address2": "町名",
    #         "address3": "N丁目",
    #         "close_dt": "",
    #     }

    #     # テスト（close_dt有の場合）
    #     output_data = instance._create_data_for_create_notify_text(input_data)
    #     assert expected_data == output_data

    #     # 入力値・期待値にclose_dtを追加
    #     input_data.close_dt = _close_dt
    #     expected_data["close_dt"] = _close_dt.strftime(r"%Y/%m/%d %H:%M")

    #     # テスト（close_dt無の場合）
    #     output_data = instance._create_data_for_create_notify_text(input_data)
    #     assert expected_data == output_data

    # def test_notify(self, mocker: MockFixture, setup_logger, setup_db):
    #     # テストデータの作成
    #     # 発生系
    #     raw_text_data_1 = niigata_datamodel.niigataRawText()
    #     raw_text_data_1.id = 1
    #     raw_text_data_1.raw_text = (
    #         "12月23日 01:23 長岡市 町名 N丁目に建物火災のため消防車が出動しました。"
    #     )
    #     raw_text_data_1.retr_dt = datetime.datetime.now()
    #     raw_text_data_1.text_pos = niigata_datamodel.TextPosition.CURR
    #     raw_text_data_1.notify_status = niigata_datamodel.NotifyStatus.NOT_YET
    #     _detail_info_1 = niigata_datamodel.niigataDisasterDetail()
    #     _detail_info_1.raw_text_id = 1
    #     _detail_info_1.main_category = niigata_datamodel.DisasterMainCategory.火災
    #     _detail_info_1.sub_category = "建物火災"
    #     _detail_info_1.open_dt = datetime.datetime(2024, 12, 23, 1, 23)
    #     _detail_info_1.close_dt = None
    #     _detail_info_1.status = niigata_datamodel.DisasterStatus.発生
    #     _detail_info_1.address1 = None
    #     _detail_info_1.address2 = "町名"
    #     _detail_info_1.address3 = "N丁目"
    #     raw_text_data_1.detail_info = _detail_info_1

    #     # 終了
    #     raw_text_data_2 = niigata_datamodel.niigataRawText()
    #     raw_text_data_2.id = 2
    #     raw_text_data_2.raw_text = (
    #         "12月23日 02:34 長岡市 町名 N丁目に救急活動のため消防車が出動しました。"
    #     )
    #     raw_text_data_2.retr_dt = datetime.datetime.now()
    #     raw_text_data_2.text_pos = niigata_datamodel.TextPosition.PAST
    #     raw_text_data_2.notify_status = niigata_datamodel.NotifyStatus.SKIPPED
    #     _detail_info_2 = niigata_datamodel.niigataDisasterDetail()
    #     _detail_info_2.raw_text_id = 2
    #     _detail_info_2.main_category = niigata_datamodel.DisasterMainCategory.救急支援
    #     _detail_info_2.sub_category = "救急活動"
    #     _detail_info_2.open_dt = datetime.datetime(2024, 12, 23, 2, 34)
    #     _detail_info_2.close_dt = None
    #     _detail_info_2.status = niigata_datamodel.DisasterStatus.終了
    #     _detail_info_2.address1 = None
    #     _detail_info_2.address2 = "町名"
    #     _detail_info_2.address3 = "N丁目"
    #     raw_text_data_2.detail_info = _detail_info_2

    #     # 通知済み
    #     raw_text_data_3 = niigata_datamodel.niigataRawText()
    #     raw_text_data_3.id = 3
    #     raw_text_data_3.raw_text = (
    #         "12月23日 00:12 長岡市 町名 N丁目に建物火災のため消防車が出動しました。"
    #     )
    #     raw_text_data_3.retr_dt = datetime.datetime.now()
    #     raw_text_data_3.text_pos = niigata_datamodel.TextPosition.CURR
    #     raw_text_data_3.notify_status = niigata_datamodel.NotifyStatus.NOTIFIED
    #     _detail_info_3 = niigata_datamodel.niigataDisasterDetail()
    #     _detail_info_3.raw_text_id = 3
    #     _detail_info_3.main_category = niigata_datamodel.DisasterMainCategory.火災
    #     _detail_info_3.sub_category = "建物火災"
    #     _detail_info_3.open_dt = datetime.datetime(2024, 12, 23, 0, 12)
    #     _detail_info_3.close_dt = None
    #     _detail_info_3.status = niigata_datamodel.DisasterStatus.発生
    #     _detail_info_3.address1 = None
    #     _detail_info_3.address2 = "町名"
    #     _detail_info_3.address3 = "N丁目"
    #     raw_text_data_3.detail_info = _detail_info_3

    #     # テストデータ登録
    #     session = util_db_manager.SESSION()
    #     try:
    #         session.add_all([raw_text_data_1, raw_text_data_2, raw_text_data_3])
    #         session.commit()

    #         # mocker登録（リクエスト処理用）
    #         mocker.patch("util_request_wrapper.post_to_discord", return_value=True)

    #         # テスト実行
    #         instance = FwdNiigata()
    #         instance._notify()

    #         # テスト結果確認（Statusにより確認）
    #         assert (
    #             session.query(niigata_datamodel.niigataRawText)
    #             .filter(niigata_datamodel.niigataRawText.id == 1)
    #             .first()
    #             .notify_status
    #             == niigata_datamodel.NotifyStatus.NOTIFIED
    #         )
    #         assert (
    #             session.query(niigata_datamodel.niigataRawText)
    #             .filter(niigata_datamodel.niigataRawText.id == 2)
    #             .first()
    #             .notify_status
    #             == niigata_datamodel.NotifyStatus.SKIPPED
    #         )
    #         assert (
    #             session.query(niigata_datamodel.niigataRawText)
    #             .filter(niigata_datamodel.niigataRawText.id == 3)
    #             .first()
    #             .notify_status
    #             == niigata_datamodel.NotifyStatus.NOTIFIED
    #         )

    #     finally:
    #         # テスト用に投入したデータを削除
    #         session.query(niigata_datamodel.niigataRawText).delete()
    #         session.query(niigata_datamodel.niigataDisasterDetail).delete()
    #         session.commit()

    # def test_notify_exception(self, mocker: MockFixture, setup_logger, setup_db):
    #     # テストデータの作成
    #     # 発生系
    #     raw_text_data_1 = niigata_datamodel.niigataRawText()
    #     raw_text_data_1.id = 1
    #     raw_text_data_1.raw_text = (
    #         "12月23日 01:23 長岡市 町名 N丁目に建物火災のため消防車が出動しました。"
    #     )
    #     raw_text_data_1.retr_dt = datetime.datetime.now()
    #     raw_text_data_1.text_pos = niigata_datamodel.TextPosition.CURR
    #     raw_text_data_1.notify_status = niigata_datamodel.NotifyStatus.NOT_YET
    #     _detail_info_1 = niigata_datamodel.niigataDisasterDetail()
    #     _detail_info_1.raw_text_id = 1
    #     _detail_info_1.main_category = niigata_datamodel.DisasterMainCategory.火災
    #     _detail_info_1.sub_category = "建物火災"
    #     _detail_info_1.open_dt = datetime.datetime(2024, 12, 23, 1, 23)
    #     _detail_info_1.close_dt = None
    #     _detail_info_1.status = niigata_datamodel.DisasterStatus.発生
    #     _detail_info_1.address1 = None
    #     _detail_info_1.address2 = "町名"
    #     _detail_info_1.address3 = "N丁目"
    #     raw_text_data_1.detail_info = _detail_info_1

    #     # テストデータ登録
    #     session = util_db_manager.SESSION()
    #     try:
    #         session.add(raw_text_data_1)
    #         session.commit()

    #         # mocker登録（リクエスト処理用）
    #         with mocker.patch(
    #             "util_request_wrapper.post_to_discord", side_effect=Exception
    #         ):
    #             with pytest.raises(Exception):
    #                 # テスト実行
    #                 instance = FwdNiigata()
    #                 instance._notify()

    #     finally:
    #         # テスト用に投入したデータを削除
    #         session.query(niigata_datamodel.niigataRawText).delete()
    #         session.query(niigata_datamodel.niigataDisasterDetail).delete()
    #         session.commit()

    # def test_get_close_dt(self, setup_logger):
    #     # 災害終了時刻が記載されていない場合
    #     _open_dt = datetime.datetime.now()
    #     _status_str = "消防車が出動しました"

    #     # テスト実行
    #     instance = FwdNiigata()
    #     assert instance._get_close_dt(_status_str, _open_dt) is None

    #     # 発生日と同日の場合
    #     _open_dt = datetime.datetime(2024, 12, 23, 1, 23)
    #     _status_str = "02:34に鎮火しました"
    #     _close_dt = datetime.datetime(2024, 12, 23, 2, 34)
    #     assert _close_dt == instance._get_close_dt(_status_str, _open_dt)

    #     # 発生日の翌日の場合
    #     _open_dt = datetime.datetime(2024, 12, 23, 23, 45)
    #     _status_str = "02:34に鎮火しました"
    #     _close_dt = datetime.datetime(2024, 12, 24, 2, 34)
    #     assert _close_dt == instance._get_close_dt(_status_str, _open_dt)

    # def test_analyze_text(self, setup_logger):
    #     # 基本テストデータ
    #     raw_text_data = niigata_datamodel.niigataRawText()
    #     raw_text_data.id = 1
    #     raw_text_data.raw_text = (
    #         "12月23日 01:23 長岡市 町名 N丁目に建物火災のため消防車が出動しました。"
    #     )
    #     raw_text_data.retr_dt = datetime.datetime(2024, 12, 23, 1, 25)
    #     raw_text_data.text_pos = niigata_datamodel.TextPosition.CURR
    #     raw_text_data.notify_status = niigata_datamodel.NotifyStatus.NOT_YET

    #     # テスト実行
    #     instance = FwdNiigata()
    #     detail_data = instance._analyze_text(raw_text_data)
    #     assert detail_data.raw_text_id == raw_text_data.id
    #     assert detail_data.main_category == niigata_datamodel.DisasterMainCategory.火災
    #     assert detail_data.sub_category == "建物火災"
    #     assert detail_data.open_dt == datetime.datetime(2024, 12, 23, 1, 23)
    #     assert detail_data.close_dt is None
    #     assert detail_data.status == niigata_datamodel.DisasterStatus.発生
    #     assert detail_data.address1 is None
    #     assert detail_data.address2 == "町名"
    #     assert detail_data.address3 == "N丁目"

    # def test_analyze_text_年またぎ(self, setup_logger):
    #     # 年またぎ用テストケース
    #     raw_text_data = niigata_datamodel.niigataRawText()
    #     raw_text_data.id = 1
    #     raw_text_data.raw_text = (
    #         "12月31日 23:59 長岡市 町名 N丁目に建物火災のため消防車が出動しました。"
    #     )
    #     raw_text_data.retr_dt = datetime.datetime(2025, 1, 1, 0, 0)
    #     raw_text_data.text_pos = niigata_datamodel.TextPosition.CURR
    #     raw_text_data.notify_status = niigata_datamodel.NotifyStatus.NOT_YET

    #     # テスト実行
    #     instance = FwdNiigata()
    #     detail_data = instance._analyze_text(raw_text_data)
    #     assert detail_data.open_dt == datetime.datetime(2024, 12, 31, 23, 59)

    # def test_analyze_text_長岡市外(self, setup_logger):
    #     # 長岡市外用テストケース（市名）
    #     raw_text_data = niigata_datamodel.niigataRawText()
    #     raw_text_data.id = 1
    #     raw_text_data.raw_text = (
    #         "12月23日 01:23 見附市 町名 に市外応援火災のため消防車が出動しました。"
    #     )
    #     raw_text_data.retr_dt = datetime.datetime(2024, 12, 23, 1, 25)
    #     raw_text_data.text_pos = niigata_datamodel.TextPosition.CURR
    #     raw_text_data.notify_status = niigata_datamodel.NotifyStatus.NOT_YET

    #     # テスト実行
    #     instance = FwdNiigata()
    #     detail_data = instance._analyze_text(raw_text_data)
    #     assert detail_data.address1 == "見附市"
    #     assert detail_data.address2 == "町名"
    #     assert detail_data.address3 is None

    #     # 長岡市外用テストケース（高速）
    #     raw_text_data = niigata_datamodel.niigataRawText()
    #     raw_text_data.id = 1
    #     raw_text_data.raw_text = (
    #         "12月23日 01:23 高速 北陸道 下りに高速車両火災のため消防車が出動しました。"
    #     )
    #     raw_text_data.retr_dt = datetime.datetime(2024, 12, 23, 1, 25)
    #     raw_text_data.text_pos = niigata_datamodel.TextPosition.CURR
    #     raw_text_data.notify_status = niigata_datamodel.NotifyStatus.NOT_YET

    #     # テスト実行
    #     instance = FwdNiigata()
    #     detail_data = instance._analyze_text(raw_text_data)
    #     assert detail_data.address1 == "高速"
    #     assert detail_data.address2 == "北陸道"
    #     assert detail_data.address3 == "下り"

    # def test_analyze_text_災害種別バリエーション(self, setup_logger):
    #     # 基本テストケース
    #     raw_text_data = niigata_datamodel.niigataRawText()
    #     raw_text_data.id = 1
    #     raw_text_data.retr_dt = datetime.datetime(2024, 12, 23, 1, 25)
    #     raw_text_data.text_pos = niigata_datamodel.TextPosition.CURR
    #     raw_text_data.notify_status = niigata_datamodel.NotifyStatus.NOT_YET

    #     # 火災（火災種別一覧は例規集より引用／一部、出動情報に掲載の文字列に合わせて改変）
    #     choices = (
    #         "建物火災",
    #         "高層建物火災",
    #         "病院火災",
    #         "危険物火災",
    #         "林野火災",
    #         "高速法面火災",
    #         "車両火災",
    #         "電柱火災",
    #         "高速車両火災",
    #         "トンネル火災",
    #         "地下駐火災",
    #         "市外応援火災",
    #         "特命火災",  # 掲載実績はないが念のためテスト
    #     )
    #     for _sub_category in choices:
    #         # テスト実行
    #         raw_text_data.raw_text = f"12月23日 01:23 長岡市 町名 N丁目に{_sub_category}のため消防車が出動しました。"
    #         instance = FwdNiigata()
    #         detail_data = instance._analyze_text(raw_text_data)
    #         assert (
    #             detail_data.main_category == niigata_datamodel.DisasterMainCategory.火災
    #         )
    #         assert detail_data.sub_category == _sub_category

    #     # 救助（救助は一律「救助活動」）
    #     raw_text_data.raw_text = (
    #         "12月23日 01:23 長岡市 町名 N丁目に救助活動のため消防車が出動しました。"
    #     )
    #     instance = FwdNiigata()
    #     detail_data = instance._analyze_text(raw_text_data)
    #     assert detail_data.main_category == niigata_datamodel.DisasterMainCategory.救助
    #     assert detail_data.sub_category == "救助活動"

    #     # 警戒（警戒種別一覧は例規集より引用／一部、出動情報に掲載の文字列に合わせて改変）
    #     # ※無言警戒、自火報警戒は「警戒活動」として掲載される
    #     choices = (
    #         "警戒活動",
    #         "ガス漏れ警戒",
    #         "油漏れ警戒",
    #         "枯草警戒",
    #         "地滑り警戒",
    #         "特命警戒",  # 掲載実績はないが念のためテスト
    #     )
    #     for _sub_category in choices:
    #         # テスト実行
    #         raw_text_data.raw_text = f"12月23日 01:23 長岡市 町名 N丁目に{_sub_category}のため消防車が出動しました。"
    #         instance = FwdNiigata()
    #         detail_data = instance._analyze_text(raw_text_data)
    #         assert (
    #             detail_data.main_category == niigata_datamodel.DisasterMainCategory.警戒
    #         )
    #         assert detail_data.sub_category == _sub_category

    #     # 救急支援（救急支援は一律「救急活動」）
    #     raw_text_data.raw_text = (
    #         "12月23日 01:23 長岡市 町名 N丁目に救急活動のため消防車が出動しました。"
    #     )
    #     instance = FwdNiigata()
    #     detail_data = instance._analyze_text(raw_text_data)
    #     assert (
    #         detail_data.main_category == niigata_datamodel.DisasterMainCategory.救急支援
    #     )
    #     assert detail_data.sub_category == "救急活動"

    #     # 災害種別不明
    #     raw_text_data.raw_text = "12月23日 01:23 長岡市 町名 N丁目に※未定義の災害※のため消防車が出動しました。"
    #     instance = FwdNiigata()
    #     detail_data = instance._analyze_text(raw_text_data)
    #     assert (
    #         detail_data.main_category == niigata_datamodel.DisasterMainCategory.その他
    #     )
    #     assert detail_data.sub_category == "※未定義の災害※"

    # def test_analyze_text_災害状態バリエーション(self, setup_logger):
    #     # 基本テストケース
    #     raw_text_data = niigata_datamodel.niigataRawText()
    #     raw_text_data.id = 1
    #     raw_text_data.retr_dt = datetime.datetime(2024, 12, 23, 1, 25)
    #     raw_text_data.text_pos = niigata_datamodel.TextPosition.CURR
    #     raw_text_data.notify_status = niigata_datamodel.NotifyStatus.NOT_YET

    #     # 発生
    #     raw_text_data.raw_text = (
    #         "12月23日 01:23 長岡市 町名 N丁目に火災のため消防車が出動しました。"
    #     )
    #     instance = FwdNiigata()
    #     detail_data = instance._analyze_text(raw_text_data)
    #     assert detail_data.status == niigata_datamodel.DisasterStatus.発生

    #     # 終了（一般）
    #     raw_text_data.text_pos = niigata_datamodel.TextPosition.PAST
    #     instance = FwdNiigata()
    #     detail_data = instance._analyze_text(raw_text_data)
    #     assert detail_data.status == niigata_datamodel.DisasterStatus.終了

    #     # 救助終了
    #     raw_text_data.raw_text = (
    #         "12月23日 01:23 長岡市 町名 N丁目の救助活動は02:34に救助終了しました。"
    #     )
    #     instance = FwdNiigata()
    #     detail_data = instance._analyze_text(raw_text_data)
    #     assert detail_data.status == niigata_datamodel.DisasterStatus.救助終了

    #     # 消火不要
    #     raw_text_data.raw_text = (
    #         "12月23日 01:23 長岡市 町名 N丁目の建物火災は消火の必要はありませんでした。"
    #     )
    #     instance = FwdNiigata()
    #     detail_data = instance._analyze_text(raw_text_data)
    #     assert detail_data.status == niigata_datamodel.DisasterStatus.消火不要

    #     # 鎮圧
    #     raw_text_data.raw_text = (
    #         "12月23日 01:23 長岡市 町名 N丁目の建物火災は02:34に鎮圧しました。"
    #     )
    #     instance = FwdNiigata()
    #     detail_data = instance._analyze_text(raw_text_data)
    #     assert detail_data.status == niigata_datamodel.DisasterStatus.鎮圧

    #     # 鎮火
    #     raw_text_data.raw_text = (
    #         "12月23日 01:23 長岡市 町名 N丁目の建物火災は02:34に鎮火しました。"
    #     )
    #     instance = FwdNiigata()
    #     detail_data = instance._analyze_text(raw_text_data)
    #     assert detail_data.status == niigata_datamodel.DisasterStatus.鎮火

    #     # Default: 終了
    #     raw_text_data.raw_text = (
    #         "12月23日 01:23 長岡市 町名 N丁目の建物火災は※不明なステータス※。"
    #     )
    #     instance = FwdNiigata()
    #     detail_data = instance._analyze_text(raw_text_data)
    #     assert detail_data.status == niigata_datamodel.DisasterStatus.終了

    # def test_analyze_text_解析失敗(self, setup_logger):
    #     # 基本テストケース
    #     raw_text_data = niigata_datamodel.niigataRawText()
    #     raw_text_data.id = 1
    #     raw_text_data.retr_dt = datetime.datetime(2024, 12, 23, 1, 25)
    #     raw_text_data.text_pos = niigata_datamodel.TextPosition.CURR
    #     raw_text_data.notify_status = niigata_datamodel.NotifyStatus.NOT_YET

    #     # 一回目の解析失敗
    #     raw_text_data.raw_text = "※解析失敗※"
    #     instance = FwdNiigata()
    #     with pytest.raises(ValueError):
    #         instance._analyze_text(raw_text_data)

    #     # 二回目の解析失敗
    #     raw_text_data.raw_text = "12月23日 01:23 長岡市 ※解析失敗※。"
    #     instance = FwdNiigata()
    #     with pytest.raises(ValueError):
    #         instance._analyze_text(raw_text_data)

    # def test_analyze(self, setup_logger, setup_db):
    #     # テストデータを追加する
    #     raw_text_datas = []
    #     # 1件目：発生
    #     _raw_text_data = niigata_datamodel.niigataRawText()
    #     _raw_text_data.id = 1
    #     _raw_text_data.retr_dt = datetime.datetime(2024, 12, 23, 1, 4)
    #     _raw_text_data.text_pos = niigata_datamodel.TextPosition.CURR
    #     _raw_text_data.notify_status = niigata_datamodel.NotifyStatus.NOT_YET
    #     _raw_text_data.raw_text = (
    #         "12月23日 01:02 長岡市 町名 N丁目に建物火災のため消防車が出動しました。"
    #     )
    #     _raw_text_data.detail_info = None
    #     raw_text_datas.append(_raw_text_data)
    #     # 2件目：終了
    #     _raw_text_data = niigata_datamodel.niigataRawText()
    #     _raw_text_data.id = 2
    #     _raw_text_data.retr_dt = datetime.datetime(2024, 12, 23, 1, 4)
    #     _raw_text_data.text_pos = niigata_datamodel.TextPosition.PAST
    #     _raw_text_data.notify_status = niigata_datamodel.NotifyStatus.NOT_YET
    #     _raw_text_data.raw_text = (
    #         "12月23日 01:01 長岡市 町名 N丁目に建物火災のため消防車が出動しました。"
    #     )
    #     _raw_text_data.detail_info = None
    #     raw_text_datas.append(_raw_text_data)
    #     # 3件目：発生（解析済み）
    #     _raw_text_data = niigata_datamodel.niigataRawText()
    #     _raw_text_data.id = 3
    #     _raw_text_data.retr_dt = datetime.datetime(2024, 12, 23, 1, 4)
    #     _raw_text_data.text_pos = niigata_datamodel.TextPosition.CURR
    #     _raw_text_data.notify_status = niigata_datamodel.NotifyStatus.SKIPPED
    #     _raw_text_data.raw_text = (
    #         "12月23日 01:00 長岡市 町名 N丁目に建物火災のため消防車が出動しました。"
    #     )
    #     _detail_data = niigata_datamodel.niigataDisasterDetail()
    #     _detail_data.raw_text_id = 3
    #     _detail_data.main_category = niigata_datamodel.DisasterMainCategory.火災
    #     _detail_data.sub_category = "建物火災"
    #     _detail_data.open_dt = datetime.datetime(2024, 12, 23, 1, 0)
    #     _detail_data.close_dt = None
    #     _detail_data.status = niigata_datamodel.DisasterStatus.発生
    #     _detail_data.address1 = None
    #     _detail_data.address2 = "町名"
    #     _detail_data.address3 = "N丁目"
    #     _raw_text_data.detail_info = _detail_data
    #     raw_text_datas.append(_raw_text_data)
    #     # DBに登録
    #     session = util_db_manager.SESSION()
    #     try:
    #         session.add_all(raw_text_datas)
    #         session.commit()

    #         # テスト実行
    #         instance = FwdNiigata()
    #         instance._analyze()
    #         results = session.query(niigata_datamodel.niigataRawText).all()

    #         # 1件目：detail_dataが登録され、通知不要が設定されていないこと
    #         assert results[0].detail_info is not None
    #         assert results[0].notify_status == niigata_datamodel.NotifyStatus.NOT_YET

    #         # 2件目：detail_dataが登録され、通知不要が設定されていること
    #         assert results[1].detail_info is not None
    #         assert results[1].notify_status == niigata_datamodel.NotifyStatus.SKIPPED

    #         # 3件目：実行前と同じ状態であること
    #         assert results[2] == raw_text_datas[2]

    #     finally:
    #         # テスト用に投入したデータを削除
    #         session.query(niigata_datamodel.niigataRawText).delete()
    #         session.query(niigata_datamodel.niigataDisasterDetail).delete()
    #         session.commit()

    # def test_analyze_exception(self, mocker: MockFixture, setup_logger, setup_db):
    #     # テストデータを追加する
    #     # 1件目：発生
    #     _raw_text_data = niigata_datamodel.niigataRawText()
    #     _raw_text_data.id = 1
    #     _raw_text_data.retr_dt = datetime.datetime(2024, 12, 23, 1, 4)
    #     _raw_text_data.text_pos = niigata_datamodel.TextPosition.CURR
    #     _raw_text_data.notify_status = niigata_datamodel.NotifyStatus.NOT_YET
    #     _raw_text_data.raw_text = (
    #         "12月23日 01:02 長岡市 町名 N丁目に建物火災のため消防車が出動しました。"
    #     )
    #     _raw_text_data.detail_info = None
    #     session = util_db_manager.SESSION()
    #     try:
    #         session.add(_raw_text_data)
    #         session.commit()

    #         # テスト実行
    #         instance = FwdNiigata()
    #         with mocker.patch(
    #             "niigata_main.FwdNiigata._analyze_text", side_effect=ValueError
    #         ):
    #             with pytest.raises(ValueError):
    #                 instance._analyze()

    #     finally:
    #         # テスト用に投入したデータを削除
    #         session.query(niigata_datamodel.niigataRawText).delete()
    #         session.query(niigata_datamodel.niigataDisasterDetail).delete()
    #         session.commit()

    # def test_commit_disaster_list_curr_通常収集(
    #     self, mocker: MockFixture, setup_logger, setup_db
    # ):
    #     try:
    #         # テストデータ読み込み
    #         input_file_path = (
    #             Path(__file__).parents[1]
    #             / "tests_resource"
    #             / "niigata_webtext_1_expected_curr.txt"
    #         )
    #         webpage_text_curr = input_file_path.read_text(encoding="utf-8")

    #         # テスト実行
    #         instance = FwdNiigata()
    #         instance._commit_disaster_list_curr(
    #             instance._cleansing_webtext(webpage_text_curr)
    #         )

    #         # テスト結果を取得し確認
    #         session = util_db_manager.SESSION()
    #         results = session.query(niigata_datamodel.niigataRawText).all()
    #         assert len(results) == 2
    #         assert (
    #             results[0].raw_text
    #             == "01月01日 05:49 長岡市 〇〇 2丁目に建物火災のため消防車が出動しました。"
    #         )
    #         assert results[0].notify_status == niigata_datamodel.NotifyStatus.NOT_YET
    #         assert (
    #             results[1].raw_text
    #             == "01月01日 05:50 長岡市 〇〇 1丁目に救急活動のため消防車が出動しました。"
    #         )
    #         assert results[1].notify_status == niigata_datamodel.NotifyStatus.NOT_YET

    #     finally:
    #         # テスト結果として保存されたデータを削除
    #         session = util_db_manager.SESSION()
    #         session.query(niigata_datamodel.niigataRawText).delete()
    #         session.query(niigata_datamodel.niigataDisasterDetail).delete()
    #         session.commit()

    # def test_commit_disaster_list_curr_過去収集(
    #     self, mocker: MockFixture, setup_logger, setup_db
    # ):
    #     try:
    #         # テストデータ読み込み
    #         input_file_path = (
    #             Path(__file__).parents[1]
    #             / "tests_resource"
    #             / "niigata_webtext_1_expected_curr.txt"
    #         )
    #         webpage_text_curr = input_file_path.read_text(encoding="utf-8")

    #         # テスト実行
    #         instance = FwdNiigata()
    #         instance._commit_disaster_list_curr(
    #             instance._cleansing_webtext(webpage_text_curr),
    #             datetime.datetime(2024, 1, 1, 5, 51),
    #         )

    #         # テスト結果を取得し確認
    #         session = util_db_manager.SESSION()
    #         results = session.query(niigata_datamodel.niigataRawText).all()
    #         assert len(results) == 2
    #         assert (
    #             results[0].raw_text
    #             == "01月01日 05:49 長岡市 〇〇 2丁目に建物火災のため消防車が出動しました。"
    #         )
    #         assert results[0].notify_status == niigata_datamodel.NotifyStatus.SKIPPED
    #         assert (
    #             results[1].raw_text
    #             == "01月01日 05:50 長岡市 〇〇 1丁目に救急活動のため消防車が出動しました。"
    #         )
    #         assert results[1].notify_status == niigata_datamodel.NotifyStatus.SKIPPED

    #     finally:
    #         # テスト結果として保存されたデータを削除
    #         session = util_db_manager.SESSION()
    #         session.query(niigata_datamodel.niigataRawText).delete()
    #         session.query(niigata_datamodel.niigataDisasterDetail).delete()
    #         session.commit()

    # def test_commit_disaster_list_curr_exception(
    #     self, mocker: MockFixture, setup_logger, setup_db
    # ):
    #     with mocker.patch("re.findall", side_effect=Exception):
    #         with pytest.raises(Exception):
    #             instance = FwdNiigata()
    #             instance._commit_disaster_list_curr("dummy")

    # def test_commit_disaster_list_past_通常収集(
    #     self, mocker: MockFixture, setup_logger, setup_db
    # ):
    #     try:
    #         # テストデータ読み込み
    #         input_file_path = (
    #             Path(__file__).parents[1]
    #             / "tests_resource"
    #             / "niigata_webtext_1_expected_past.txt"
    #         )
    #         webpage_text_past = input_file_path.read_text(encoding="utf-8")

    #         # テスト実行
    #         instance = FwdNiigata()
    #         instance._commit_disaster_list_past(
    #             instance._cleansing_webtext(webpage_text_past)
    #         )

    #         # テスト結果を取得し確認
    #         session = util_db_manager.SESSION()
    #         results = session.query(niigata_datamodel.niigataRawText).all()
    #         assert len(results) == 20
    #         assert (
    #             results[0].raw_text
    #             == "12月29日 00:04 長岡市 〇〇〇 の建物火災は01:18に鎮圧しました。"
    #         )
    #         assert results[0].notify_status == niigata_datamodel.NotifyStatus.NOT_YET
    #         assert (
    #             results[-1].raw_text
    #             == "12月31日 10:17 長岡市 〇〇 4丁目に救急活動のため消防車が出動しました。"
    #         )
    #         assert results[1].notify_status == niigata_datamodel.NotifyStatus.NOT_YET

    #     finally:
    #         # テスト結果として保存されたデータを削除
    #         session = util_db_manager.SESSION()
    #         session.query(niigata_datamodel.niigataRawText).delete()
    #         session.query(niigata_datamodel.niigataDisasterDetail).delete()
    #         session.commit()

    # def test_commit_disaster_list_past_過去収集(
    #     self, mocker: MockFixture, setup_logger, setup_db
    # ):
    #     try:
    #         # テストデータ読み込み
    #         input_file_path = (
    #             Path(__file__).parents[1]
    #             / "tests_resource"
    #             / "niigata_webtext_1_expected_past.txt"
    #         )
    #         webpage_text_past = input_file_path.read_text(encoding="utf-8")

    #         # テスト実行
    #         instance = FwdNiigata()
    #         instance._commit_disaster_list_past(
    #             instance._cleansing_webtext(webpage_text_past),
    #             datetime.datetime(2024, 1, 1, 5, 51),
    #         )

    #         # テスト結果を取得し確認
    #         session = util_db_manager.SESSION()
    #         results = session.query(niigata_datamodel.niigataRawText).all()
    #         assert len(results) == 20
    #         assert (
    #             results[0].raw_text
    #             == "12月29日 00:04 長岡市 〇〇〇 の建物火災は01:18に鎮圧しました。"
    #         )
    #         assert results[0].notify_status == niigata_datamodel.NotifyStatus.SKIPPED
    #         assert (
    #             results[-1].raw_text
    #             == "12月31日 10:17 長岡市 〇〇 4丁目に救急活動のため消防車が出動しました。"
    #         )
    #         assert results[1].notify_status == niigata_datamodel.NotifyStatus.SKIPPED

    #     finally:
    #         # テスト結果として保存されたデータを削除
    #         session = util_db_manager.SESSION()
    #         session.query(niigata_datamodel.niigataRawText).delete()
    #         session.query(niigata_datamodel.niigataDisasterDetail).delete()
    #         session.commit()

    # def test_commit_disaster_list_past_exception(
    #     self, mocker: MockFixture, setup_logger, setup_db
    # ):
    #     with mocker.patch("re.findall", side_effect=Exception):
    #         with pytest.raises(Exception):
    #             instance = FwdNiigata()
    #             instance._commit_disaster_list_past("dummy")

    # def test_execute(self, mocker: MockFixture, setup_logger):
    #     instance = FwdNiigata()
    #     # 各関数の内部はそれぞれのUTでテストするため、内部処理はmock化する
    #     with (
    #         mocker.patch("util_request_wrapper.download_webpage", return_value="dummy"),
    #         mocker.patch(
    #             "niigata_main.FwdNiigata._cleansing_webtext", return_value="dummy"
    #         ),
    #         mocker.patch(
    #             "niigata_main.FwdNiigata._split_webtext",
    #             return_value=("dummy", "dummy"),
    #         ),
    #         mocker.patch(
    #             "niigata_main.FwdNiigata._commit_disaster_list_curr", return_value=None
    #         ),
    #         mocker.patch(
    #             "niigata_main.FwdNiigata._commit_disaster_list_curr", return_value=None
    #         ),
    #         mocker.patch("niigata_main.FwdNiigata._analyze", return_value=None),
    #         mocker.patch("niigata_main.FwdNiigata._notify", return_value=None),
    #     ):
    #         execute_result = instance.execute()
    #         assert execute_result is True

    # def test_execute_exception(self, mocker: MockFixture, setup_logger):
    #     instance = FwdNiigata()
    #     with mocker.patch(
    #         "util_request_wrapper.download_webpage", side_effect=requests.HTTPError
    #     ):
    #         execute_result = instance.execute()
    #         assert execute_result is False

    # def test_store_old_data(self, mocker: MockFixture, setup_logger, setup_db):
    #     instance = FwdNiigata()
    #     session = util_db_manager.SESSION()
    #     try:
    #         # テスト実行
    #         _text_dir = (
    #             Path(__file__).parents[1] / "tests_resource" / "store_old_data_test"
    #         )
    #         instance.store_old_data(_text_dir.as_posix())

    #         # テスト結果（登録件数）を確認
    #         # 1ファイル目：発生1、過去20
    #         # 2ファイル目：発生0、過去1
    #         assert (1 + 20 + 0 + 1) == session.query(
    #             niigata_datamodel.niigataRawText
    #         ).count()

    #         # 各レコードの確認
    #         results = session.query(niigata_datamodel.niigataRawText).all()

    #         # 1件目
    #         assert (
    #             results[0].raw_text
    #             == "01月01日 14:04 長岡市 町名 に救急活動のため消防車が出動しました。"
    #         )
    #         assert results[0].retr_dt == datetime.datetime(2024, 1, 1, 14, 7)
    #         assert results[0].text_pos == niigata_datamodel.TextPosition.CURR
    #         assert results[0].notify_status == niigata_datamodel.NotifyStatus.SKIPPED
    #         assert results[0].detail_info is not None

    #         # 2件目
    #         assert (
    #             results[1].raw_text
    #             == "12月26日 20:34 長岡市 町名 1丁目に警戒活動のため消防車が出動しました。"
    #         )
    #         assert results[1].retr_dt == datetime.datetime(2024, 1, 1, 14, 7)
    #         assert results[1].text_pos == niigata_datamodel.TextPosition.PAST
    #         assert results[1].notify_status == niigata_datamodel.NotifyStatus.SKIPPED
    #         assert results[1].detail_info is not None

    #         # 22件目（2ファイル目で新規登録したデータ）
    #         assert (
    #             results[21].raw_text
    #             == "01月01日 14:04 長岡市 町名 に救急活動のため消防車が出動しました。"
    #         )
    #         assert results[21].retr_dt == datetime.datetime(2024, 1, 1, 15, 30)
    #         assert results[21].text_pos == niigata_datamodel.TextPosition.PAST
    #         assert results[21].notify_status == niigata_datamodel.NotifyStatus.SKIPPED
    #         assert results[21].detail_info is not None

    #     finally:
    #         # テスト結果として保存されたデータを削除
    #         session.query(niigata_datamodel.niigataRawText).delete()
    #         session.query(niigata_datamodel.niigataDisasterDetail).delete()
    #         session.commit()

    # def test_store_old_data_不正ファイルあり(
    #     self, mocker: MockFixture, setup_logger, setup_db
    # ):
    #     instance = FwdNiigata()
    #     session = util_db_manager.SESSION()
    #     try:
    #         _text_dir = (
    #             Path(__file__).parents[1]
    #             / "tests_resource"
    #             / "store_old_data_test_invalid_files"
    #         )

    #         # テスト対象関数を実行
    #         instance.store_old_data(_text_dir.as_posix())

    #         # テスト結果を確認
    #         # 2ファイル目は読み込まれないため、件数は20+1=21件が期待値となる
    #         assert (20 + 1) == session.query(niigata_datamodel.niigataRawText).count()

    #     finally:
    #         # テスト結果として保存されたデータを削除
    #         session.query(niigata_datamodel.niigataRawText).delete()
    #         session.query(niigata_datamodel.niigataDisasterDetail).delete()
    #         session.commit()

    # def test_store_old_data_exception(
    #     self, mocker: MockFixture, setup_logger, setup_db
    # ):
    #     instance = FwdNiigata()
    #     session = util_db_manager.SESSION()
    #     try:
    #         _text_dir = (
    #             Path(__file__).parents[1] / "tests_resource" / "store_old_data_test"
    #         )

    #         # テスト対象関数を実行
    #         with mocker.patch(
    #             "niigata_main.FwdNiigata._commit_disaster_list_curr",
    #             side_effect=Exception,
    #         ):
    #             result = instance.store_old_data(_text_dir.as_posix())
    #             assert result is False

    #     finally:
    #         # テスト結果として保存されたデータを削除
    #         session.query(niigata_datamodel.niigataRawText).delete()
    #         session.query(niigata_datamodel.niigataDisasterDetail).delete()
    #         session.commit()
