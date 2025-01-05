import datetime
from enum import Enum

from fwdutil import database_manager
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.ext.declarative import declarative_base

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
    CURR = 1
    PAST = 2


class AnalyzeStatus(Enum):
    NOT_YET = 1
    ANALYZED = 2


class NotifyStatus(Enum):
    SKIPPED = 0
    NOT_YET = 1
    NOTIFIED = 2


class NagaokaRawText(Base):
    __tablename__ = "nagaoka_raw_text"
    id = Column(Integer, primary_key=True)
    raw_text = Column(String, nullable=False)
    retr_dt = Column(DateTime, nullable=False, default=datetime.datetime.now())
    text_pos = Column(Integer, nullable=False)
    analyze_status = Column(
        Integer, nullable=False, default=AnalyzeStatus.NOT_YET.value
    )
    notify_status = Column(Integer, nullable=False, default=NotifyStatus.NOT_YET.value)
