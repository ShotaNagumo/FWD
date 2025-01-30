import datetime
from enum import Enum, auto

import sqlalchemy
from fwdutil import database_manager
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


def create_table_all():
    Base.metadata.create_all(bind=database_manager.ENGINE)


class DatabaseInfo(Base):
    """データベース自身の情報を管理する

    Args:
        Base (_type_): declarative_base() によって取得した基底クラス
    """

    __tablename__ = "_database_info"
    id = Column(Integer, primary_key=True)
    version = Column(Integer, nullable=False)


class TextPosition(Enum):
    CURR = auto()
    PAST = auto()


class NotifyStatus(Enum):
    SKIPPED = auto()
    NOT_YET = auto()
    NOTIFIED = auto()


class DisasterMainCategory(Enum):
    火災 = auto()
    救助 = auto()
    警戒 = auto()
    救急支援 = auto()
    その他 = auto()


class DisasterStatus(Enum):
    発生 = auto()
    救助終了 = auto()
    消火不要 = auto()
    鎮圧 = auto()
    鎮火 = auto()
    終了 = auto()


class NagaokaRawText(Base):
    __tablename__ = "nagaoka_raw_text"
    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_text = Column(String, nullable=False)
    retr_dt = Column(DateTime, nullable=False, default=datetime.datetime.now())
    text_pos = Column(sqlalchemy.Enum(TextPosition), nullable=False)
    notify_status = Column(
        sqlalchemy.Enum(NotifyStatus), nullable=False, default=NotifyStatus.NOT_YET
    )
    detail_info = relationship("NagaokaDisasterDetail", uselist=False)


class NagaokaDisasterDetail(Base):
    __tablename__ = "nagaoka_disaster_detail"

    """ "nagaoka_raw_text"テーブルのID
    """
    raw_text_id = Column(
        Integer, ForeignKey("nagaoka_raw_text.id", ondelete="CASCADE"), primary_key=True
    )
    """災害種別
    """
    main_category = Column(sqlalchemy.Enum(DisasterMainCategory), nullable=False)
    """災害種別詳細
    """
    sub_category = Column(String, nullable=True)
    """災害発生時刻
    """
    open_dt = Column(DateTime, nullable=False)
    """災害終了時刻
    """
    close_dt = Column(DateTime, nullable=True)
    """災害状態
    """
    status = Column(sqlalchemy.Enum(DisasterStatus), nullable=False)
    """住所1（長岡市以外の場合の都市名）
    """
    address1 = Column(String, nullable=True)
    """住所2（町名、道路名）
    """
    address2 = Column(String, nullable=False)
    """住所3（丁目、道路方向）
    """
    address3 = Column(String, nullable=True)
