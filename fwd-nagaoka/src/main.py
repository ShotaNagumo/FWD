import datetime
import logging
import re
from pathlib import Path
from typing import Final

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

    def _analyze_disaster_text(self, alt_year=None):
        session: Session = database_manager.SESSION()

        # 分析対象のNagaokaRawText一覧をDBから取得する
        not_analyzed_list = (
            session.query(NagaokaRawText)
            .filter(NagaokaRawText.detail_info == sqlalchemy.null())
            .all()
        )

        # 分析処理を実行する
        self._logger.info(f"Not Analyzed: {len(not_analyzed_list)}")
        for raw_text_data in not_analyzed_list:
            detail_data = self._analyzelogic(
                raw_text_data.raw_text, raw_text_data.id, alt_year
            )

            # 解析結果をコミットする
            session.add(detail_data)
            session.commit()

    def _analyzelogic(
        self, disaster_text: str, raw_text_id: int, alt_year=None
    ) -> NagaokaDisasterDetail:
        # 解析結果を格納するインスタンス生成
        detail_data = NagaokaDisasterDetail()

        # raw_text_idを設定する
        detail_data.raw_text_id = raw_text_id

        # 一回目の解析（発生時刻、都市名を解析する）
        m_1st = re.match(
            r"(?P<month>\d{2})月(?P<day>\d{2})日 (?P<hour>\d{2}):(?P<minute>\d{2}) (?P<city>\S+?) (?P<next>.+)。$",
            disaster_text,
        )

        # 災害発生時刻の年を決定する
        # TODO: 年末を考慮した処理の実装
        open_year = alt_year if alt_year else datetime.datetime.now().year

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
        # self._logger.info(f'{m_1st.group("next")=}')
        # self._logger.info(
        #     f'{m_1st.group("next")=}, {m_2nd.group("address")=}, {m_2nd.group("category")=}, {m_2nd.group("status")=}'
        # )

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

        # 住所を決定する
        # TODO: より詳細な住所解析
        detail_data.address2 = m_2nd.group("address")

        # 状態を決定する
        # TODO: 終了時の判定
        # TODO: close_dtに設定する時刻の解析（鎮圧、鎮火、救助終了）
        status_str = m_2nd.group("status")
        if re.search(r"消防車が出動しました", status_str):
            detail_data.status = DisasterStatus.発生
        elif re.search(r"救助終了しました", status_str):
            detail_data.status = DisasterStatus.救助終了
        elif re.search(r"消火の必要はありませんでした", status_str):
            detail_data.status = DisasterStatus.消火不要
        elif re.search(r"鎮圧しました", status_str):
            detail_data.status = DisasterStatus.鎮圧
        elif re.search(r"鎮火しました", status_str):
            detail_data.status = DisasterStatus.鎮火
        else:
            detail_data.status = DisasterStatus.終了

        # TODO: 以下の実装は仮（NotNull制約を満たすため）
        # detail_data.address2 = "○○"
        # detail_data.address3 = "N丁目"

        return detail_data


if __name__ == "__main__":
    create_table_all()
    f = FwdWNagaoka()
