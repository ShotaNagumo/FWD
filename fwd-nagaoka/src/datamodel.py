import datetime
from enum import Enum

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
    CURR = 1
    PAST = 2


class NotifyStatus(Enum):
    SKIPPED = 0
    NOT_YET = 1
    NOTIFIED = 2


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
    raw_text_id = Column(
        Integer, ForeignKey("nagaoka_raw_text.id", ondelete="CASCADE"), primary_key=True
    )
    open_dt = Column(DateTime, nullable=False)
    close_dt = Column(DateTime, nullable=True)
