import datetime
import logging
import re
from pathlib import Path
from typing import Final, Optional

import sqlalchemy
from fwdutil import config, database_manager, request_wrapper
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm.session import Session

from fwdnagaoka.datamodel import (
    DisasterMainCategory,
    DisasterStatus,
    NagaokaDisasterDetail,
    NagaokaRawText,
    NotifyStatus,
    TextPosition,
    create_table_all,
)


class FwdNagaoka:
    WEBPAGE_URL: Final[str] = "http://www.nagaoka-fd.com/fire/saigai/saigaipc.html"
    WEBPAGE_ENC: Final[str] = "sjis"

    def __init__(self):
        """コンストラクタ"""
        self._logger = logging.getLogger("fwd.nagaoka")
        _template_dir = Path(__file__).parents[2] / "resource" / "template"
        self._j2_env = Environment(loader=FileSystemLoader(_template_dir))
        self._webhook_url = config.get_webhook_url("nagaoka")

    @staticmethod
    def setup():
        """テーブルを作成する"""
        create_table_all()

    def execute(self):
        """災害情報の取得から通知までの一連の処理を実行する"""
        try:
            self._logger.info("execute() 実行開始")
            # Webから災害情報テキストを取得
            webpage_text = request_wrapper.download_webpage(
                FwdNagaoka.WEBPAGE_URL, FwdNagaoka.WEBPAGE_ENC
            )

            # 災害情報テキストを前処理・分割
            webpage_text_dev = self._split_webtext(
                self._cleansing_webtext(webpage_text)
            )

            # 災害情報（現在発生している災害）をDBへ登録
            self._commit_disaster_list_curr(webpage_text_dev[0])

            # 災害情報（過去の災害情報）をDBへ登録
            self._commit_disaster_list_past(webpage_text_dev[1])

            # 災害情報の解析
            self._analyze()

            # 災害情報の通知
            self._notify()

            self._logger.info("execute() 実行完了")
        except Exception:
            self._logger.exception("execute() 実行失敗")

    def store_old_data(self, text_dir: str):
        # TODO: 過去データのインポート機能追加
        self._logger.info("store_old_data() 実行開始")
        try:
            # 指定されたディレクトリ内の対象ファイル一覧を検索する
            text_dir_path = Path(text_dir)
            text_files = [_ for _ in text_dir_path.glob("*.txt")]

            # テキストファイルから災害情報を読み込み、解析処理を行う
            self._logger.info("災害情報の登録開始")
            for index, text_file in enumerate(text_files):
                # ファイル名から実行時刻を取得する
                filename_m = re.match(
                    r"(?P<date_time_str>\d{8}_\d{4})\.txt", text_file.name
                )
                if not filename_m:
                    self._logger.info(f"ファイル名不正のためスキップ：{text_file.name}")
                    continue
                else:
                    self._logger.info(
                        f"災害情報の登録[{index + 1}/{len(text_files)}]：{text_file.name}"
                    )
                retrieve_time = datetime.datetime.strptime(
                    filename_m.group("date_time_str"), "%Y%m%d_%H%M"
                )

                # ファイルから読み込む
                webpage_text = text_file.read_text(encoding="utf-8")

                # 災害情報テキストを前処理・分割
                webpage_text_dev = self._split_webtext(
                    self._cleansing_webtext(webpage_text)
                )

                # 災害情報（現在発生している災害）をDBへ登録
                self._commit_disaster_list_curr(webpage_text_dev[0], retrieve_time)

                # 災害情報（過去の災害情報）をDBへ登録
                self._commit_disaster_list_past(webpage_text_dev[1], retrieve_time)

            # 災害情報の解析
            self._logger.info("災害情報の登録完了・解析開始")
            self._analyze()
            self._logger.info("災害情報の解析完了")

        except Exception:
            self._logger.exception("store_old_data() 実行失敗")
        self._logger.info("store_old_data() 実行終了")

    def _cleansing_webtext(self, webpage_text: str) -> str:
        """htmlテキスト解析前に、前処理として整形処理を行う
        Args:
            webpage_text (str): 災害情報を含むWebページのテキスト

        Returns:
            str: 前処理後のWebページテキスト
        """
        return re.sub(r"\u3000", " ", webpage_text)

    def _split_webtext(self, webpage_text: str) -> list[str]:
        """htmlテキストを、「現在発生している災害」が記載されている部分と「過去の災害」が記載されている部分に分割する

        Args:
            webpage_text (str): 災害情報を含むWebページのテキスト

        Raises:
            ValueError: 処理に失敗した場合

        Returns:
            list[str]: [0]: 現在発生している災害の文字列、[1]: 過去の災害の文字列
        """

        # 「現在」「過去」それぞれの災害情報を検索する
        pat = re.compile(
            r".+↓現在発生している災害↓(.+)↑現在発生している災害↑.+↓過去の災害経過情報↓(.+)↑過去の災害経過情報↑.+",
            re.DOTALL,
        )

        # 検索に失敗した場合はValueErrorとする（災害情報掲示の仕様変更などの場合を想定）
        if not (m := pat.match(webpage_text)):
            raise ValueError("現在/過去の災害情報分割失敗")

        # 検索結果を返却
        return [
            m.group(1),
            m.group(2),
        ]

    def _commit_disaster_list_curr(self, webpage_text_curr: str, execute_dt=None):
        """「現在発生している災害」の文字列を抽出してDBに登録する

        Args:
            webpage_text_curr (str): 「現在発生している災害」の文字列
            execute_dt (datetime.datetime, optional): 文字列を取得した日時. Defaults to None.
        """

        session: Session = database_manager.SESSION()

        # 災害情報の文字列を検索する
        try:
            # execute_dt の指定状況に応じ、登録する情報を決定する
            retrieve_dt = datetime.datetime.now() if execute_dt is None else execute_dt
            notify_stat = (
                NotifyStatus.NOT_YET if execute_dt is None else NotifyStatus.SKIPPED
            )

            # 文字列解析
            matches = re.findall(
                r"<span>(\d{2}月\d{2}日.+?。)</span>", webpage_text_curr
            )

            for match_str in matches[::-1]:
                # 登録済みかを確認する
                registered = bool(
                    session.query(NagaokaRawText)
                    .filter(NagaokaRawText.raw_text == match_str)
                    .filter(NagaokaRawText.text_pos == TextPosition.CURR)
                    .count()
                )

                # 登録されていない場合は登録する
                if not registered:
                    # 登録する情報を作成する
                    raw_text_data = NagaokaRawText(
                        raw_text=match_str,
                        retr_dt=retrieve_dt,
                        text_pos=TextPosition.CURR,
                        notify_status=notify_stat,
                    )
                    # DBに送信する
                    session.add(raw_text_data)

                    # DBにコミットする
                    session.commit()
                    self._logger.info(
                        f"「現在」の災害情報登録完了 ID=[{raw_text_data.id}]"
                    )

        except Exception:
            # 解析に失敗した場合はロールバックする
            self._logger.error("「現在」の災害情報登録失敗")
            session.rollback()
            raise
        finally:
            session.close()

    def _commit_disaster_list_past(self, webpage_text_past: str, execute_dt=None):
        """「過去の災害」の文字列を抽出してDBに登録する

        Args:
            webpage_text_past (str): 「過去の災害」の文字列
            execute_dt (datetime.datetime, optional): 文字列を取得した日時. Defaults to None.
        """
        session: Session = database_manager.SESSION()

        try:
            # execute_dt の指定状況に応じ、登録する情報を決定する
            retrieve_dt = datetime.datetime.now() if execute_dt is None else execute_dt
            notify_stat = (
                NotifyStatus.NOT_YET if execute_dt is None else NotifyStatus.SKIPPED
            )

            # 災害情報の文字列を検索する
            matches = re.findall(
                r"<span>(\d{2}月\d{2}日.+?。)</span>", webpage_text_past
            )
            for match_str in matches[::-1]:
                # 登録済みかを確認する
                registered = bool(
                    session.query(NagaokaRawText)
                    .filter(NagaokaRawText.raw_text == match_str)
                    .filter(NagaokaRawText.text_pos == TextPosition.PAST)
                    .count()
                )
                # 登録されていない場合は登録する
                if not registered:
                    # 登録する情報を作成する
                    raw_text_data = NagaokaRawText(
                        raw_text=match_str,
                        retr_dt=retrieve_dt,
                        text_pos=TextPosition.PAST,
                        notify_status=notify_stat,
                    )
                    session.add(raw_text_data)

                    # DBにコミットする
                    session.commit()
                    self._logger.info(
                        f"「過去」の災害情報登録完了 ID=[{raw_text_data.id}]"
                    )

        except Exception:
            # 解析に失敗した場合はロールバックする
            self._logger.error("「過去」の災害情報登録失敗")
            session.rollback()
            raise
        finally:
            session.close()

    def _analyze(self):
        """災害文字列の解析を実行する"""

        session: Session = database_manager.SESSION()

        try:
            # 分析対象のNagaokaRawText一覧をDBから取得する
            not_analyzed_list = (
                session.query(NagaokaRawText)
                .filter(NagaokaRawText.detail_info == sqlalchemy.null())
                .all()
            )

            # 分析処理を実行する
            for raw_text_data in not_analyzed_list:
                self._logger.info(f"ID=[{raw_text_data.id}] の文字列解析処理開始")
                detail_data = self._analyze_text(raw_text_data)

                # statusが「終了」の場合は通知不要を設定する
                if detail_data.status == DisasterStatus.終了:
                    raw_text_data.notify_status = NotifyStatus.SKIPPED

                # 分析結果をDBに送信しコミットする
                session.add(detail_data)
                session.commit()
                self._logger.info(f"ID=[{raw_text_data.id}] の文字列解析処理完了")

        except Exception:
            # 解析に失敗した場合は処理をロールバックする
            self._logger.error("文字列解析処理失敗")
            session.rollback()
            raise
        finally:
            session.close()

    def _analyze_text(self, raw_text_data: NagaokaRawText) -> NagaokaDisasterDetail:
        """災害文字列の解析ロジック

        Args:
            raw_text_data (NagaokaRawText): 解析対象の災害情報

        Raises:
            ValueError: 解析処理に失敗した場合

        Returns:
            NagaokaDisasterDetail: 解析結果情報
        """
        try:
            # 解析結果を格納するインスタンス生成
            detail_data = NagaokaDisasterDetail()

            # raw_text_idを設定する
            detail_data.raw_text_id = raw_text_data.id

            # 一回目の解析（発生時刻、都市名を解析する）
            m_1st = re.match(
                r"(?P<month>\d{2})月(?P<day>\d{2})日 (?P<hour>\d{2}):(?P<minute>\d{2}) (?P<city>\S+?) (?P<next>.+)。$",
                raw_text_data.raw_text,
            )
            if not m_1st:
                raise ValueError("一回目の解析失敗")

            # 災害発生時刻の年を決定する
            # 基本的にはanalyze_dt の年を設定するが、
            # analyze_dt.month < m_1st.month の場合は前年と判定して
            # analyze_dt.year - 1 を設定する
            open_year = raw_text_data.retr_dt.year
            if raw_text_data.retr_dt.month < int(m_1st.group("month")):
                open_year -= 1

            # 災害発生時刻を決定する
            detail_data.open_dt = datetime.datetime(
                year=open_year,
                month=int(m_1st.group("month")),
                day=int(m_1st.group("day")),
                hour=int(m_1st.group("hour")),
                minute=int(m_1st.group("minute")),
            )

            # 都市名を決定する
            # "長岡市"以外の場合はその都市名を設定し、"長岡市"の場合はNoneを設定
            detail_data.address1 = (
                m_1st.group("city") if m_1st.group("city") != "長岡市" else None
            )

            # 二回目の解析（災害種別、住所、状態を解析する）
            m_2nd = re.match(
                r"(?P<address>.+?)(に|の)(?P<category>\S+?)(は|のため)(?P<status>.+)$",
                m_1st.group("next"),
            )
            if not m_2nd:
                raise ValueError("二回目の解析失敗")

            # 災害種別を決定する
            category_str = m_2nd.group("category")
            if re.search(r"火災", category_str):
                detail_data.main_category = DisasterMainCategory.火災
            elif re.search(r"救助", category_str):
                detail_data.main_category = DisasterMainCategory.救助
            elif re.search(r"警戒", category_str):
                detail_data.main_category = DisasterMainCategory.警戒
            elif re.search(r"救急", category_str):
                detail_data.main_category = DisasterMainCategory.救急支援
            else:
                detail_data.main_category = DisasterMainCategory.その他

            # 災害種別詳細を設定する
            detail_data.sub_category = category_str

            # 住所を空白で分割しaddress2とaddress3を設定する
            # address3に該当する部分が無い場合はNULLとする
            addr2, addr3 = m_2nd.group("address").split(" ")
            detail_data.address2 = addr2
            if addr3:
                detail_data.address3 = addr3

            # 状態を決定する
            status_str = m_2nd.group("status")
            if re.search(r"消防車が出動しました", status_str):
                if raw_text_data.text_pos == TextPosition.CURR:
                    detail_data.status = DisasterStatus.発生
                else:
                    detail_data.status = DisasterStatus.終了
            elif re.search(r"救助終了しました", status_str):
                detail_data.status = DisasterStatus.救助終了
                detail_data.close_dt = self._get_close_dt(
                    status_str, detail_data.open_dt
                )
            elif re.search(r"消火の必要はありませんでした", status_str):
                detail_data.status = DisasterStatus.消火不要
            elif re.search(r"鎮圧しました", status_str):
                detail_data.status = DisasterStatus.鎮圧
                detail_data.close_dt = self._get_close_dt(
                    status_str, detail_data.open_dt
                )
            elif re.search(r"鎮火しました", status_str):
                detail_data.status = DisasterStatus.鎮火
                detail_data.close_dt = self._get_close_dt(
                    status_str, detail_data.open_dt
                )
            else:
                detail_data.status = DisasterStatus.終了
            # 解析結果を返却する

            return detail_data

        except Exception:
            # 解析に失敗した場合
            self._logger.error("災害文字列の解析に失敗")
            raise

    def _get_close_dt(
        self, status_str: str, open_dt: datetime.datetime
    ) -> Optional[datetime.datetime]:
        """災害終了時刻を解析する

        Args:
            status_str (str): 終了時刻が含まれた文字列
            open_dt (datetime.datetime): 災害発生時刻情報

        Returns:
            Optional[datetime.datetime]: 災害終了時刻情報。含まれていなかった場合はNone。
        """
        # 文字列から災害終了時刻の時・分を解析する
        close_dt_m = re.match(r"(?P<hour>\d{2}):(?P<minute>\d{2}).+$", status_str)

        # 災害終了時刻を決定する
        if not close_dt_m:
            # 災害終了時刻が記載されていない場合はNoneを返却する
            return None
        else:
            # 災害発生時刻、文字列解析結果を考慮して終了時刻を決定する

            # いったん、災害発生と同日に終了したものとして時刻を設定する
            close_dt = datetime.datetime(
                year=open_dt.year,
                month=open_dt.month,
                day=open_dt.day,
                hour=int(close_dt_m.group("hour")),
                minute=int(close_dt_m.group("minute")),
            )

            # close_dt < open_dt の場合は、翌日に終了したとして一日進める
            if close_dt < open_dt:
                close_dt += datetime.timedelta(days=1)

            # 終了時刻を返却する
            return close_dt

    def _notify(self):
        """通知処理を実行する"""
        session: Session = database_manager.SESSION()

        try:
            # 通知が必要な災害情報を検索する
            not_notified_list = (
                session.query(NagaokaRawText)
                .filter(NagaokaRawText.notify_status.is_(NotifyStatus.NOT_YET))
                .all()
            )

            # 通知を実行する
            for raw_text_data in not_notified_list:
                # 通知文の作成
                notify_text = self._create_notify_text(raw_text_data.detail_info)
                # 通知の実行
                request_wrapper.post_to_discord(self._webhook_url, notify_text)
                # 状態を通知済みに更新
                raw_text_data.notify_status = NotifyStatus.NOTIFIED
                session.commit()

        except Exception:
            # 通知に失敗した場合は処理をロールバックする
            self._logger.error("通知処理失敗")
            session.rollback()
            raise
        finally:
            session.close()

    def _create_notify_text(self, detail_data: NagaokaDisasterDetail) -> str:
        """通知文を作成する

        Args:
            detail_data (NagaokaDisasterDetail): 解析結果データ

        Returns:
            str: 作成した通知文
        """
        try:
            template = self._j2_env.get_template("notify.j2")
            data = self._create_data_for_create_notify_text(detail_data)
            notify_text = template.render(data)
            return notify_text
        except Exception:
            self._logger.error("通知文の作成に失敗")
            raise

    def _create_data_for_create_notify_text(
        self, detail_data: NagaokaDisasterDetail
    ) -> dict[str, str]:
        """通知文を作成するために使用するデータへの変換を行う

        Args:
            detail_data (NagaokaDisasterDetail): 解析結果データ

        Returns:
            dict[str, str]: 通知文を作成するために使用するデータ
        """
        datetime_format_str = r"%Y/%m/%d %H:%M"
        data = {
            "main_category": detail_data.main_category.name,
            "sub_category": detail_data.sub_category,
            "open_dt": detail_data.open_dt.strftime(datetime_format_str),
            "status": detail_data.status.name,
            "address1": detail_data.address1,
            "address2": detail_data.address2,
            "address3": detail_data.address3,
        }
        if detail_data.close_dt:
            data["close_dt"] = detail_data.close_dt.strftime(datetime_format_str)
        else:
            data["close_dt"] = ""

        return data
