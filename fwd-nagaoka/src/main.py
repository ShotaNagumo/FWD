import datetime
import logging
import re
from pathlib import Path
from typing import Final

import sqlalchemy
from datamodel import (
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

    def _analyze_disaster_text(self):
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
            # 分析結果をもとに詳細情報データを作成する
            # TODO: 以下の実装は仮
            detail_data = NagaokaDisasterDetail(
                raw_text_id=raw_text_data.id,
                open_dt=datetime.datetime.now(),
                close_dt=datetime.datetime.now(),
            )

            # 解析結果をコミットする
            session.add(detail_data)
            session.commit()


if __name__ == "__main__":
    create_table_all()
    f = FwdWNagaoka()
