import datetime
import logging
import re
import unicodedata
from pathlib import Path
from typing import Final

import common_datamodel
import niigata_datamodel
import sqlalchemy
import util_config
import util_db_manager
import util_request_wrapper
import yaml
from jinja2 import Environment, FileSystemLoader
from niigata_datamodel import (
    DisasterMainCategory,
    DisasterStatus,
    NiigataDisasterDetail,
    NiigataNoticeText,
    NiigataRawText,
    NoticeType,
    NotifyStatus,
    OpenCloseStatus,
)
from sqlalchemy.orm.session import Session


class FwdNiigata:
    WEBPAGE_URL: Final[str] = "https://niigata119.city.niigata.lg.jp/"
    WEBPAGE_ENC: Final[str] = "utf8"

    def __init__(self):
        """コンストラクタ"""
        # logger
        self._logger = logging.getLogger("fwd.niigata")

        # 通知文テンプレート
        _template_dir = util_config.get_resource_dir() / "niigata" / "template"
        self._j2_env = Environment(loader=FileSystemLoader(_template_dir))

        # 通知URL
        self._webhook_url = util_config.get_webhook_url("niigata")

        # 住所補完定義
        _complement_dict_path = (
            util_config.get_resource_dir() / "niigata" / "complement_address_dict.yaml"
        )
        self._complement_dict = yaml.safe_load(
            _complement_dict_path.read_text(encoding="utf-8")
        )

    @staticmethod
    def setup():
        """テーブルを作成する"""
        common_datamodel.create_table_all()
        niigata_datamodel.create_table_all()

    def execute(self) -> bool:
        """災害情報の取得から通知までの一連の処理を実行する

        Returns:
            bool: 処理結果（正常終了：True, 異常終了：False）
        """
        try:
            self._logger.info("execute() 実行開始")

            # Webから災害情報テキストを取得
            webpage_text = util_request_wrapper.download_webpage(
                FwdNiigata.WEBPAGE_URL, FwdNiigata.WEBPAGE_ENC
            )

            # 災害情報テキストを分割
            webpage_text_div = self._split_webtext(webpage_text)

            # 案内情報をDBへ登録する
            self._commit_disaster_list_notice(webpage_text_div[0])

            # 終了情報をDBへ登録する
            self._commit_disaster_list_close(webpage_text_div[1])

            # 鎮火情報をDBへ登録する
            self._commit_disaster_list_chinka(webpage_text_div[1])

            # 災害情報をDBへ登録する
            self._commit_disaster_list_curr(webpage_text_div[1])

            # 災害情報の解析
            self._analyze()

            # 案内情報・災害情報の通知
            self._notify()

            # 正常終了
            self._logger.info("execute() 実行完了")
            return True
        except Exception:
            # 異常終了
            self._logger.exception("execute() 実行失敗")
            return False

    def store_old_data(self, text_dir: str) -> bool:
        """過去データをインポートする

        Args:
            text_dir (str): 過去データが格納されているディレクトリパス

        Returns:
            bool: 処理結果（正常終了：True, 異常終了：False）
        """
        self._logger.info("store_old_data() 実行開始")
        try:
            # 指定されたディレクトリ内の対象ファイル一覧を検索する
            text_dir_path = Path(text_dir)
            # text_files = [_ for _ in text_dir_path.glob("*.txt")]
            text_files = [_ for _ in text_dir_path.glob("202401*.txt")]

            # テキストファイルから災害情報を読み込み、解析処理を行う
            self._logger.info("災害情報の登録・解析開始")
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
                webpage_text = unicodedata.normalize("NFKC", webpage_text)
                webpage_text_div = self._split_webtext(webpage_text)

                # 案内情報をDBへ登録する
                self._commit_disaster_list_notice(webpage_text_div[0], retrieve_time)

                # 終了情報をDBへ登録する
                self._commit_disaster_list_close(webpage_text_div[1], retrieve_time)

                # 鎮火情報をDBへ登録する
                self._commit_disaster_list_chinka(webpage_text_div[1], retrieve_time)

                # 災害情報をDBへ登録する
                self._commit_disaster_list_curr(webpage_text_div[1], retrieve_time)

                # 災害情報の解析
                self._analyze()

            # 正常終了
            self._logger.info("災害情報の登録・解析完了")
            return True

        except Exception:
            # 異常終了
            self._logger.exception("store_old_data() 実行失敗")
            return False

    def _split_webtext(self, webpage_text: str) -> list[str]:
        """htmlテキストを、「案内情報表示エリア」と「最新出動情報表示エリア」
           に分割する

        Args:
            webpage_text (str): 災害情報を含むWebページのテキスト

        Raises:
            ValueError: 処理に失敗した場合

        Returns:
            list[str]: [0]: 案内情報の文字列、[1]: 最新出動情報の文字列
        """

        # 案内情報表示エリアの内容を取得する
        pat_notice = re.compile(
            r"""(.+)<div id="topInformation"><h2>\s*(\S+?)\s*</h2>(.+)""", re.DOTALL
        )
        if not (m_notice := pat_notice.match(webpage_text)):
            notice_text = ""
        else:
            notice_text = m_notice.group(2)

        # 最新出動情報エリアの内容を取得する
        pat_curr = re.compile(r"""(.+)<p id="newInfo">(.+?)</p>(.+)""", re.DOTALL)
        if not (m_curr := pat_curr.match(webpage_text)):
            # 検索に失敗した場合はValueErrorとする（災害情報掲示の仕様変更などの場合を想定）
            raise ValueError("案内情報/最新出動情報の災害情報分割失敗")
        curr_text = m_curr.group(2)

        # 検索結果を返却
        return [
            notice_text,
            curr_text,
        ]

    def _commit_disaster_list_notice(self, webpage_text_notice: str, execute_dt=None):
        """案内情報をDBに登録する

        Args:
            webpage_text_notice (str): 案内情報の文字列
            execute_dt (datetime.datetime, optional): 文字列を取得した日時. Defaults to None.
        """

        session = util_db_manager.SESSION()
        try:
            # 案内情報が空の場合は処理不要
            if not webpage_text_notice:
                return

            # execute_dt の指定状況に応じ、登録する情報を決定する
            retrieve_dt = datetime.datetime.now() if execute_dt is None else execute_dt
            notify_stat = (
                NotifyStatus.NOT_YET if execute_dt is None else NotifyStatus.SKIPPED
            )

            # 登録済みかを確認する
            registered = bool(
                session.query(NiigataNoticeText)
                .filter(NiigataNoticeText.raw_text == webpage_text_notice)
                .count()
            )

            # 登録されていない場合は登録する
            if not registered:
                # 登録する情報を作成する
                notice_text_data = NiigataNoticeText(
                    notice_type=NoticeType.一般案内,
                    raw_text=webpage_text_notice,
                    retr_dt=retrieve_dt,
                    notify_status=notify_stat,
                )
                # DBに送信する
                session.add(notice_text_data)

                # DBにコミットする
                session.commit()
                self._logger.info(f"案内情報登録完了 ID=[{notice_text_data.id}]")

        except Exception:
            # 解析に失敗した場合はロールバックする
            self._logger.error("案内情報情報登録失敗")
            session.rollback()
            raise
        finally:
            session.close()

    def _commit_disaster_list_chinka(self, webpage_text_curr: str, execute_dt=None):
        """「最新出動情報」の文字列より、鎮火情報を抽出してDBに登録する

        Args:
            webpage_text_curr (str): 「最新出動情報」の文字列
            execute_dt (datetime.datetime, optional): 文字列を取得した日時. Defaults to None.
        """
        session: Session = util_db_manager.SESSION()

        try:
            # execute_dt の指定状況に応じ、登録する情報を決定する
            retrieve_dt = datetime.datetime.now() if execute_dt is None else execute_dt
            notify_stat = (
                NotifyStatus.NOT_YET if execute_dt is None else NotifyStatus.SKIPPED
            )

            # 入力文字列を"<br>"で分割する
            for chinka_text in re.split(r"<br>", webpage_text_curr):
                # 災害情報の文字列を検索する
                matches = re.search(
                    r"\d{2}時\d{2}分頃、.+?付近の火災は鎮火しました。", chinka_text
                )

                # 鎮火情報無しの場合は次へ進む
                if not matches:
                    continue

                # 登録済みかを確認する
                # 12時間以内の鎮火情報を対象とする（鎮火情報には日付情報が無いため、
                # 同一住所・同一時分の鎮火情報を混同する可能性があり、これを防ぐため）
                threshold_dt = retrieve_dt - datetime.timedelta(hours=12)
                registered = bool(
                    session.query(NiigataNoticeText)
                    .filter(NiigataNoticeText.raw_text == matches.group(0))
                    .filter(NiigataNoticeText.notice_type == NoticeType.鎮火情報)
                    .filter(NiigataNoticeText.retr_dt >= threshold_dt)
                    .count()
                )
                # 登録されていない場合は登録する
                if not registered:
                    # 登録する情報を作成する
                    notice_text_data = NiigataNoticeText(
                        notice_type=NoticeType.鎮火情報,
                        raw_text=matches.group(0),
                        retr_dt=retrieve_dt,
                        notify_status=notify_stat,
                    )
                    session.add(notice_text_data)

                    # DBにコミットする
                    session.commit()
                    self._logger.info(
                        f"「鎮火」の災害情報登録完了 ID=[{notice_text_data.id}]"
                    )

        except Exception:
            # 解析に失敗した場合はロールバックする
            self._logger.error("「鎮火」の災害情報登録失敗")
            session.rollback()
            raise
        finally:
            session.close()

    def _commit_disaster_list_curr(self, webpage_text_curr: str, execute_dt=None):
        """「最新出動情報」の文字列より、災害発生状況を抽出してDBに登録する

        Args:
            webpage_text_curr (str): 「最新出動情報」の文字列
            execute_dt (datetime.datetime, optional): 文字列を取得した日時. Defaults to None.
        """

        session: Session = util_db_manager.SESSION()

        # 災害情報の文字列を検索する
        try:
            # execute_dt の指定状況に応じ、登録する情報を決定する
            retrieve_dt = datetime.datetime.now() if execute_dt is None else execute_dt
            notify_stat = (
                NotifyStatus.NOT_YET if execute_dt is None else NotifyStatus.SKIPPED
            )

            # 文字列解析
            matches = re.findall(
                r"(\d{2}月\d{2}日\d{2}時\d{2}分頃、.+?出動しています。)",
                webpage_text_curr,
            )

            for match_str in matches[::-1]:
                # 登録済みかを確認する
                registered = bool(
                    session.query(NiigataRawText)
                    .filter(NiigataRawText.raw_text == match_str)
                    .count()
                )

                # 登録されていない場合は登録する
                if not registered:
                    # 登録する情報を作成する
                    raw_text_data = NiigataRawText(
                        raw_text=match_str,
                        retr_dt=retrieve_dt,
                        notify_status=notify_stat,
                    )
                    # DBに送信する
                    session.add(raw_text_data)

                    # DBにコミットする
                    session.commit()
                    self._logger.info(
                        f"「発生」の災害情報登録完了 ID=[{raw_text_data.id}]"
                    )

        except Exception:
            # 解析に失敗した場合はロールバックする
            self._logger.error("「発生」の災害情報登録失敗")
            session.rollback()
            raise
        finally:
            session.close()

    def _commit_disaster_list_close(self, webpage_text_curr: str, execute_dt=None):
        """災害の終了を確認し、終了情報をDBに登録する

        Args:
            webpage_text_curr (str): 「最新出動情報」の文字列
            execute_dt (datetime.datetime, optional): 文字列を取得した日時. Defaults to None.
        """
        session: Session = util_db_manager.SESSION()
        retrieve_dt = datetime.datetime.now() if execute_dt is None else execute_dt

        # 終了情報を登録する
        try:
            # 発生中の災害情報一覧を取得する
            target_list = session.query(NiigataRawText).filter(
                NiigataRawText.open_close_status == OpenCloseStatus.発生中
            )

            for target in target_list:
                # raw_text が webpage_text_curr に含まれているかを確認する
                is_closed = not bool(re.search(target.raw_text, webpage_text_curr))
                if is_closed:
                    # 終了情報を登録する
                    close_data = NiigataRawText()
                    close_data.raw_text = target.raw_text
                    close_data.retr_dt = retrieve_dt
                    close_data.notify_status = NotifyStatus.SKIPPED
                    close_data.open_close_status = OpenCloseStatus.終了
                    close_detail_data = NiigataDisasterDetail()
                    close_detail_data.main_category = target.detail_info.main_category
                    close_detail_data.open_dt = target.detail_info.open_dt
                    close_detail_data.status = DisasterStatus.終了
                    close_detail_data.address1 = target.detail_info.address1
                    close_detail_data.address2 = target.detail_info.address2
                    close_detail_data.address3 = target.detail_info.address3
                    close_data.detail_info = close_detail_data
                    session.add(close_data)
                    session.commit()

                    # targetの災害情報状態を更新する
                    target.open_close_status = OpenCloseStatus.発生
                    session.add(target)
                    session.commit()

        except Exception:
            # 解析に失敗した場合はロールバックする
            self._logger.error("「終了」の災害情報登録失敗")
            session.rollback()
            raise
        finally:
            session.close()

    def _analyze(self):
        """災害文字列の解析を実行する"""

        session: Session = util_db_manager.SESSION()

        try:
            # 分析対象のNiigataRawText一覧をDBから取得する
            not_analyzed_list = (
                session.query(NiigataRawText)
                .filter(NiigataRawText.detail_info == sqlalchemy.null())
                .all()
            )

            # 分析処理を実行する
            for raw_text_data in not_analyzed_list:
                self._logger.info(f"ID=[{raw_text_data.id}] の文字列解析処理開始")
                detail_data = self._analyze_text(raw_text_data)

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

    def _analyze_text(self, raw_text_data: NiigataRawText) -> NiigataDisasterDetail:
        """災害文字列の解析ロジック

        Args:
            raw_text_data (NiigataRawText): 解析対象の災害情報

        Raises:
            ValueError: 解析処理に失敗した場合

        Returns:
            NiigataDisasterDetail: 解析結果情報
        """
        try:
            # 解析結果を格納するインスタンス生成
            detail_data = NiigataDisasterDetail()

            # raw_text_idを設定する
            detail_data.raw_text_id = raw_text_data.id

            # 一回目の解析（住所詳細以外の情報を解析する）
            m_1st = re.match(
                r"(?P<month>\d{2})月(?P<day>\d{2})日(?P<hour>\d{2})時(?P<minute>\d{2})分頃、"
                r"(?P<address>.+?)付近で(?P<category>\S+?)のため出動しています。$",
                raw_text_data.raw_text,
            )
            if not m_1st:
                raise ValueError("一回目の解析失敗（発生文字列）")

            # 災害発生時刻の年を決定する
            # 基本的にはanalyze_dt の年を設定するが、
            # analyze_dt.month < m_1st.month の場合は前年と判定して
            # analyze_dt.year - 1 を設定する
            open_year = raw_text_data.retr_dt.year
            if raw_text_data.retr_dt.month < int(m_1st.group("month")):
                open_year -= 1

            # 災害発生時刻を設定する
            detail_data.open_dt = datetime.datetime(
                year=open_year,
                month=int(m_1st.group("month")),
                day=int(m_1st.group("day")),
                hour=int(m_1st.group("hour")),
                minute=int(m_1st.group("minute")),
            )

            # 災害種別を設定する
            category_str = m_1st.group("category")
            if re.search("火災", category_str):
                detail_data.main_category = DisasterMainCategory.火災
            elif re.search("救助", category_str):
                detail_data.main_category = DisasterMainCategory.救助
            elif re.search("警戒", category_str):
                detail_data.main_category = DisasterMainCategory.警戒
            elif re.search("救急", category_str):
                detail_data.main_category = DisasterMainCategory.救急支援
            elif re.search("応援", category_str):
                detail_data.main_category = DisasterMainCategory.応援
            else:
                detail_data.main_category = DisasterMainCategory.その他

            # 災害状態（ここでは「発生」固定）
            detail_data.status = DisasterStatus.発生

            # 二回目の解析（住所詳細）
            if m_addr_1 := re.search(
                r"(?P<district>\S+区)(?P<town>\S+)", m_1st.group("address")
            ):
                # パターン1：〇区〇町（N丁目）の場合
                # address1：区名
                detail_data.address1 = m_addr_1.group("district")
                if m_2nd_1_town := re.match(
                    r"(?P<town>\S+?)(?P<chome>\d+丁目)", m_addr_1.group("town")
                ):
                    # 〇町N丁目の場合
                    # address2: 町名
                    # address3: 丁目
                    detail_data.address2 = m_2nd_1_town.group("town")
                    detail_data.address3 = m_2nd_1_town.group("chome")
                else:
                    # 〇町の場合
                    # address2: 町名
                    detail_data.address2 = m_addr_1.group("town")
            elif m_addr_2 := re.match(
                r"(?P<road>\S+?BP)(?P<direction>\S+?方向)(?P<start>\S+?)から(?P<end>\S+)",
                m_1st.group("address"),
            ):
                # パターン2：バイパス
                # address1：バイパス名
                detail_data.address1 = re.sub("BP", "バイパス", m_addr_2.group("road"))
                # address2：方向
                detail_data.address2 = m_addr_2.group("direction")
                # address3：始点->終点
                _start = m_addr_2.group("start")
                _end = m_addr_2.group("end")
                _end = re.sub("方向車線", "", _end)
                _end = re.sub("方向車", "", _end)
                _end = re.sub("方向", "", _end)
                _end = re.sub("方", "", _end)
                _end = self._complement_address(_end)
                detail_data.address3 = f"{_start}->{_end}"
            elif m_addr_3 := re.match(
                r"北陸自動車道(?P<direction>(上|下)り)(?P<road>.+)",
                m_1st.group("address"),
            ):
                # パターン3：高速道（北陸道）
                # address1：道路名（北陸道）
                detail_data.address1 = "北陸道"
                # address2：方向
                detail_data.address2 = m_addr_3.group("direction")
                # address3："road"マッチ部分から道路名、方向を削除し残った部分
                _addr3 = re.sub("北陸自動車道", "", m_addr_3.group("road"))
                _addr3 = re.sub("北陸道", "", _addr3)
                _addr3 = re.sub(m_addr_3.group("direction"), "", _addr3)
                _addr3 = re.sub(r"\s", "", _addr3)
                _addr3 = self._complement_address(_addr3)
                detail_data.address3 = _addr3
            elif m_addr_4 := re.match(
                r"磐越自動車道(?P<direction>(上|下)り)(?P<road>.+)",
                m_1st.group("address"),
            ):
                # パターン4：高速道（磐越道）
                # address1：道路名（磐越道）
                detail_data.address1 = "磐越道"
                # address2：方向
                detail_data.address2 = m_addr_4.group("direction")
                # address3："road"マッチ部分から道路名、方向を削除し残った部分
                _addr3 = re.sub("磐越自動車道", "", m_addr_4.group("road"))
                _addr3 = re.sub("磐越道", "", _addr3)
                _addr3 = re.sub(m_addr_4.group("direction"), "", _addr3)
                _addr3 = re.sub(r"\s", "", _addr3)
                _addr3 = self._complement_address(_addr3)
                detail_data.address3 = _addr3
            elif m_addr_5 := re.match(
                r"日本海東北自動車道(?P<direction_symbol>(△|▼))(?P<road>.+)",
                m_1st.group("address"),
            ):
                # パターン5：高速道（日東道）
                # address1：道路名（日東道）
                detail_data.address1 = "日東道"
                # address2：方向
                if m_addr_5.group("direction_symbol") == "△":
                    detail_data.address2 = "上り"
                else:
                    detail_data.address2 = "下り"
                # address3："road"マッチ部分から道路名、方向を削除し残った部分
                _addr3 = re.sub("日本海東北自動車道", "", m_addr_5.group("road"))
                _addr3 = re.sub("日東道", "", _addr3)
                _addr3 = re.sub("上", "", _addr3)
                _addr3 = re.sub("下", "", _addr3)
                _addr3 = re.sub("り", "", _addr3)
                _addr3 = re.sub(r"\s", "", _addr3)
                if _addr3:
                    _addr3 = self._complement_address(_addr3)
                    detail_data.address3 = _addr3
            elif m_addr_6 := re.match(
                r"角田山(?P<point>.+)",
                m_1st.group("address"),
            ):
                # パターン6：角田山
                # address1：地点名（角田山）
                detail_data.address1 = "角田山"
                # address2："point"マッチ部分から"角田山"等を削除して残った部分
                _addr2 = re.sub("角田山", "", m_addr_6.group("point"))
                _addr2 = re.sub(r"\s", "", _addr2)
                if _addr2:
                    detail_data.address2 = _addr2
            elif m_addr_7 := re.match(
                r"みなとTN(?P<direction>.+?行き)(.+)",
                m_1st.group("address"),
            ):
                # パターン7：みなとトンネル
                # address1：道路名（みなとトンネル）
                detail_data.address1 = "みなとトンネル"
                # address2：directionマッチ部分
                _addr2 = re.sub("行き", "方向", m_addr_7.group("direction"))
                detail_data.address2 = _addr2
            elif m_addr_8 := re.match(
                r"トンネル(?P<tunnel>.+)",
                m_1st.group("address"),
            ):
                # パターン8：みなとトンネル以外のトンネル
                # address1：トンネル名
                detail_data.address1 = m_addr_8.group("tunnel")
            else:
                # パターン9：その他（市外など）
                _addr1 = m_1st.group("address")
                detail_data.address1 = _addr1
                if len(_addr1) % 2 == 0:
                    mid = len(_addr1) // 2
                    if _addr1[:mid] == _addr1[mid:]:
                        # 住所の前半と後半が同一内容ならその部分だけ登録する
                        detail_data.address1 = _addr1[:mid]

            # 解析結果を返却する
            return detail_data

        except Exception:
            # 解析に失敗した場合
            self._logger.error("災害文字列の解析に失敗")
            raise

    def _complement_address(self, target_address: str) -> str:
        """不完全な住所を補完する

        Args:
            target_address (str): 補完対象の住所

        Returns:
            str: 補完後の住所
        """
        # 数字のみの場合はキロポスト表記に変換する
        if re.match(r"\d{1,3}", target_address):
            return f"{target_address}KP"

        # 補完定義に含まれている場合は補完後文字列とする
        if complemented := self._complement_dict.get(target_address, None):
            return complemented

        # 補完定義に含まれていない場合はそのまま返却
        return target_address

    def _notify(self):
        """通知処理を実行する"""
        session: Session = util_db_manager.SESSION()

        try:
            # 通知が必要な案内情報を検索する
            not_notified_notice_list = (
                session.query(NiigataNoticeText)
                .filter(NiigataNoticeText.notify_status.is_(NotifyStatus.NOT_YET))
                .all()
            )

            # 通知を実行する（案内情報）
            for notice_data in not_notified_notice_list:
                # 通知文の作成
                notify_text = self._create_notify_text_notice(notice_data)
                # 通知の実行
                util_request_wrapper.post_to_discord(self._webhook_url, notify_text)
                # 状態を通知済みに更新
                notice_data.notify_status = NotifyStatus.NOTIFIED
                session.commit()

            # 通知が必要な災害情報を検索する
            not_notified_disaster_list = (
                session.query(NiigataRawText)
                .filter(NiigataRawText.notify_status.is_(NotifyStatus.NOT_YET))
                .all()
            )

            # 通知を実行する（災害情報）
            for disaster_data in not_notified_disaster_list:
                # 通知文の作成
                notify_text = self._create_notify_text_disaster(
                    disaster_data.detail_info
                )
                # 通知の実行
                util_request_wrapper.post_to_discord(self._webhook_url, notify_text)
                # 状態を通知済みに更新
                notice_data.notify_status = NotifyStatus.NOTIFIED
                session.commit()
        except Exception:
            # 通知に失敗した場合は処理をロールバックする
            self._logger.error("通知処理失敗")
            session.rollback()
            raise
        finally:
            session.close()

    def _create_notify_text_notice(self, notice_data: NiigataNoticeText) -> str:
        """通知文を作成する（案内情報）

        Args:
            notice_data (NiigataNoticeText): 案内情報データ

        Returns:
            str: 作成した通知文
        """
        try:
            template = self._j2_env.get_template("notify_notice.j2")
            data = self._create_notify_data_by_notice(notice_data)
            notify_text = template.render(data)
            return notify_text
        except Exception:
            self._logger.error("通知文の作成に失敗")
            raise

    def _create_notify_text_disaster(self, detail_data: NiigataDisasterDetail) -> str:
        """通知文を作成する（災害情報）

        Args:
            detail_data (NiigataDisasterDetail): 解析結果データ

        Returns:
            str: 作成した通知文
        """
        try:
            template = self._j2_env.get_template("notify_disaster.j2")
            data = self._create_notify_data_by_disaster(detail_data)
            notify_text = template.render(data)
            return notify_text
        except Exception:
            self._logger.error("通知文の作成に失敗")
            raise

    def _create_notify_data_by_disaster(
        self, detail_data: NiigataDisasterDetail
    ) -> dict[str, str]:
        """通知文を作成するために使用するデータへの変換を行う（災害情報）

        Args:
            detail_data (NiigataDisasterDetail): 解析結果データ

        Returns:
            dict[str, str]: 通知文を作成するために使用するデータ
        """
        datetime_format_str = r"%Y/%m/%d %H:%M"
        data = {
            "main_category": detail_data.main_category.name,
            "open_dt": detail_data.open_dt.strftime(datetime_format_str),
        }
        addr_list = []
        for addr in (detail_data.address1, detail_data.address2, detail_data.address3):
            if addr:
                addr_list.append(addr)
        data["address"] = " ".join(addr_list)

        return data

    def _create_notify_data_by_notice(
        self, notice_data: NiigataNoticeText
    ) -> dict[str, str]:
        """通知文を作成するために使用するデータへの変換を行う（案内情報）

        Args:
            notice_data (NiigataNoticeText): 案内情報データ

        Returns:
            dict[str, str]: 通知文を作成するために使用するデータ
        """
        datetime_format_str = r"%Y/%m/%d %H:%M"
        data = {
            "notice_text": notice_data.raw_text,
            "retr_dt": notice_data.retr_dt.strftime(datetime_format_str),
        }
        if notice_data.notice_type == NoticeType.一般案内:
            data["notice_title"] = "情報"
        elif notice_data.notice_type == NoticeType.鎮火情報:
            data["notice_title"] = "鎮火情報"

        return data
