import datetime
import logging
import re
from pathlib import Path
from typing import Final, Optional

import sqlalchemy
from datamodel import (
    DisasterMainCategory,
    DisasterStatus,
    NagaokaDisasterDetail,
    NagaokaRawText,
    TextPosition,
    create_table_all,
)
from fwdutil import database_manager, logger_initializer, request_wrapper
from sqlalchemy.orm.session import Session


class FwdWNagaoka:
    WEBPAGE_URL: Final[str] = "http://www.nagaoka-fd.com/fire/saigai/saigaipc.html"
    WEBPAGE_ENC: Final[str] = "sjis"

    def __init__(self):
        log_config_file = Path(__file__).parents[2] / "config" / "log_format.yaml"
        logger_initializer.initialize(log_config_file)
        self._logger = logging.getLogger("fwd.nagaoka")

        webpage_text = request_wrapper.download_webpage(
            FwdWNagaoka.WEBPAGE_URL, FwdWNagaoka.WEBPAGE_ENC
        )
        webpage_text_dev = self._split_webtext(self._cleansing_webtext(webpage_text))
        self._commit_disaster_list_curr(webpage_text_dev[0])
        self._commit_disaster_list_past(webpage_text_dev[1])
        self._analyze_disaster_text()

    def _cleansing_webtext(self, webpage_text: str) -> str:
        return re.sub(r"\u3000", " ", webpage_text)

    def _split_webtext(self, webpage_text: str) -> list[str]:
        pat = re.compile(
            r".+↓現在発生している災害↓(.+)↑現在発生している災害↑.+↓過去の災害経過情報↓(.+)↑過去の災害経過情報↑.+",
            re.DOTALL,
        )
        if not (m := pat.match(webpage_text)):
            raise ValueError()

        return [
            m.group(1),
            m.group(2),
        ]

    def _commit_disaster_list_curr(self, webpage_text_curr: str):
        matches = re.findall(r"<span>(\d{2}月\d{2}日.+?。)</span>", webpage_text_curr)
        session: Session = database_manager.SESSION()
        for m in matches[::-1]:
            registered = bool(
                session.query(NagaokaRawText)
                .filter(NagaokaRawText.raw_text == m)
                .filter(NagaokaRawText.text_pos == TextPosition.CURR)
                .count()
            )
            if not registered:
                raw_text_data = NagaokaRawText(
                    raw_text=m,
                    text_pos=TextPosition.CURR,
                )
                session.add(raw_text_data)
        session.commit()

    def _commit_disaster_list_past(self, webpage_text_past: str):
        matches = re.findall(r"<span>(\d{2}月\d{2}日.+?。)</span>", webpage_text_past)
        session: Session = database_manager.SESSION()
        for m in matches[::-1]:
            registered = bool(
                session.query(NagaokaRawText)
                .filter(NagaokaRawText.raw_text == m)
                .filter(NagaokaRawText.text_pos == TextPosition.PAST)
                .count()
            )
            if not registered:
                raw_text_data = NagaokaRawText(
                    raw_text=m,
                    text_pos=TextPosition.PAST,
                )
                session.add(raw_text_data)
        session.commit()

    def _analyze_disaster_text(self, analyze_dt=datetime.datetime.now()):
        session: Session = database_manager.SESSION()

        try:
            # 分析対象のNagaokaRawText一覧をDBから取得する
            self._logger.info("文字列解析処理開始")
            not_analyzed_list = (
                session.query(NagaokaRawText)
                .filter(NagaokaRawText.detail_info == sqlalchemy.null())
                .all()
            )

            # 分析処理を実行する
            self._logger.info(f"解析対象件数: [{len(not_analyzed_list)}]")
            for raw_text_data in not_analyzed_list:
                detail_data = self._analyzelogic(raw_text_data, analyze_dt)

                # 分析結果をDBに送信しコミットする
                session.add(detail_data)
                session.commit()

            self._logger.info("文字列解析処理完了")
        except Exception:
            # 解析に失敗した場合は処理をロールバックする
            self._logger.exception("文字列解析処理失敗")
            session.rollback()
            raise
        finally:
            session.close()

    def _analyzelogic(
        self, raw_text_data: NagaokaRawText, analyze_dt: datetime.datetime
    ) -> NagaokaDisasterDetail:
        # 解析結果を格納するインスタンス生成
        detail_data = NagaokaDisasterDetail()

        # raw_text_idを設定する
        detail_data.raw_text_id = raw_text_data.id

        # 一回目の解析（発生時刻、都市名を解析する）
        m_1st = re.match(
            r"(?P<month>\d{2})月(?P<day>\d{2})日 (?P<hour>\d{2}):(?P<minute>\d{2}) (?P<city>\S+?) (?P<next>.+)。$",
            raw_text_data.raw_text,
        )

        # 災害発生時刻の年を決定する
        # 基本的にはanalyze_dt の年を設定するが、
        # analyze_dt.month < m_1st.month の場合は前年と判定して
        # analyze_dt.year - 1 を設定する
        open_year = analyze_dt.year
        if analyze_dt.month < int(m_1st.group("month")):
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
            r"(?P<address>.+?)(に|の)(?P<category>.+?)(は|のため)(?P<status>.+)$",
            m_1st.group("next"),
        )

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
            detail_data.close_dt = self._get_close_dt(status_str, detail_data.open_dt)
        elif re.search(r"消火の必要はありませんでした", status_str):
            detail_data.status = DisasterStatus.消火不要
        elif re.search(r"鎮圧しました", status_str):
            detail_data.status = DisasterStatus.鎮圧
            detail_data.close_dt = self._get_close_dt(status_str, detail_data.open_dt)
        elif re.search(r"鎮火しました", status_str):
            detail_data.status = DisasterStatus.鎮火
            detail_data.close_dt = self._get_close_dt(status_str, detail_data.open_dt)
        else:
            detail_data.status = DisasterStatus.終了

        # 解析結果を返却する
        return detail_data

    def _get_close_dt(
        self, status_str: str, open_dt: datetime.datetime
    ) -> Optional[datetime.datetime]:
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


if __name__ == "__main__":
    create_table_all()
    f = FwdWNagaoka()
