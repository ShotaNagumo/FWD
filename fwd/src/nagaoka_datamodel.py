import datetime
from enum import Enum, auto

import sqlalchemy
import util_db_manager
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

Base = sqlalchemy.orm.declarative_base()


def create_table_all():
    Base.metadata.create_all(bind=util_db_manager.ENGINE)


class TextPosition(Enum):
    """災害情報文字列が掲載されていた位置

    Args:
        Enum (_type_): Enum基底クラス
    """

    CURR = auto()
    """「現在発生している災害」
    """

    PAST = auto()
    """「過去の災害経過情報」
    """


class NotifyStatus(Enum):
    """通知状態

    Args:
        Enum (_type_): Enum基底クラス
    """

    SKIPPED = auto()
    """通知不要
    """

    NOT_YET = auto()
    """通知未
    """

    NOTIFIED = auto()
    """通知済み
    """


class DisasterMainCategory(Enum):
    """災害種別（大分類）

    Args:
        Enum (_type_): Enum基底クラス
    """

    火災 = auto()
    """火災
    """

    救助 = auto()
    """救助
    """

    警戒 = auto()
    """警戒
    """

    救急支援 = auto()
    """救急支援
    """

    その他 = auto()
    """その他
    """


class DisasterStatus(Enum):
    """災害状態

    Args:
        Enum (_type_): Enum基底クラス
    """

    発生 = auto()
    """災害発生
    """

    救助終了 = auto()
    """救助終了
    """

    消火不要 = auto()
    """消火不要
    """

    鎮圧 = auto()
    """鎮圧
    """

    鎮火 = auto()
    """鎮火
    """

    終了 = auto()
    """終了
    """


class NagaokaRawText(Base):
    """災害情報を格納するテーブル"""

    __tablename__ = "nagaoka_raw_text"
    """テーブル名
    """

    id = Column(Integer, primary_key=True, autoincrement=True)
    """NagaokaRawText ID
    """

    raw_text = Column(String, nullable=False)
    """災害情報文字列
    """

    retr_dt = Column(DateTime, nullable=False, default=datetime.datetime.now())
    """取得時刻
    （過去データから取得した場合は、過去データが記録されているファイル名から取得した日付）
    """

    text_pos = Column(sqlalchemy.Enum(TextPosition), nullable=False)
    """災害情報文字列が保存されていた位置
    """

    notify_status = Column(
        sqlalchemy.Enum(NotifyStatus), nullable=False, default=NotifyStatus.NOT_YET
    )
    """災害情報の通知状態
    """

    detail_info = relationship("NagaokaDisasterDetail", uselist=False)
    """詳細テーブルのオブジェクト
    """


class NagaokaDisasterDetail(Base):
    __tablename__ = "nagaoka_disaster_detail"

    raw_text_id = Column(
        Integer, ForeignKey("nagaoka_raw_text.id", ondelete="CASCADE"), primary_key=True
    )
    """ "nagaoka_raw_text"テーブルのID
    """

    main_category = Column(sqlalchemy.Enum(DisasterMainCategory), nullable=False)
    """災害種別
    """

    sub_category = Column(String, nullable=True)
    """災害種別詳細
    """

    open_dt = Column(DateTime, nullable=False)
    """災害発生時刻
    """

    close_dt = Column(DateTime, nullable=True)
    """災害終了時刻
    """

    status = Column(sqlalchemy.Enum(DisasterStatus), nullable=False)
    """災害状態
    """

    address1 = Column(String, nullable=True)
    """住所1（長岡市以外の場合の都市名）
    """

    address2 = Column(String, nullable=False)
    """住所2（町名、道路名）
    """

    address3 = Column(String, nullable=True)
    """住所3（丁目、道路方向）
    """
