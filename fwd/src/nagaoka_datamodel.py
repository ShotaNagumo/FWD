import datetime
from enum import Enum, auto

import sqlalchemy
import util_db_manager
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

Base = sqlalchemy.orm.declarative_base()


def create_table_all():
    Base.metadata.create_all(bind=util_db_manager.ENGINE)


class DatabaseInfo(Base):
    """データベース自身の情報を管理する

    Args:
        Base (_type_): declarative_base() によって取得した基底クラス
    """

    """テーブル名
    """
    __tablename__ = "_database_info"

    """カラムID
    """
    id = Column(Integer, primary_key=True)

    """DBバージョン
    """
    version = Column(Integer, nullable=False)


class TextPosition(Enum):
    """災害情報文字列が掲載されていた位置

    Args:
        Enum (_type_): Enum基底クラス
    """

    """「現在発生している災害」
    """
    CURR = auto()

    """「過去の災害経過情報」
    """
    PAST = auto()


class NotifyStatus(Enum):
    """通知状態

    Args:
        Enum (_type_): Enum基底クラス
    """

    """通知不要
    """
    SKIPPED = auto()

    """通知未
    """
    NOT_YET = auto()

    """通知済み
    """
    NOTIFIED = auto()


class DisasterMainCategory(Enum):
    """災害種別（大分類）

    Args:
        Enum (_type_): Enum基底クラス
    """

    """火災
    """
    火災 = auto()

    """救助
    """
    救助 = auto()

    """警戒
    """
    警戒 = auto()

    """救急支援
    """
    救急支援 = auto()

    """その他
    """
    その他 = auto()


class DisasterStatus(Enum):
    """災害状態

    Args:
        Enum (_type_): Enum基底クラス
    """

    """災害発生
    """
    発生 = auto()

    """救助終了
    """
    救助終了 = auto()

    """消火不要
    """
    消火不要 = auto()

    """鎮圧
    """
    鎮圧 = auto()

    """鎮火
    """
    鎮火 = auto()

    """終了
    """
    終了 = auto()


class NagaokaRawText(Base):
    """災害情報を格納するテーブル"""

    """テーブル名
    """
    __tablename__ = "nagaoka_raw_text"

    """NagaokaRawText ID
    """
    id = Column(Integer, primary_key=True, autoincrement=True)

    """災害情報文字列
    """
    raw_text = Column(String, nullable=False)

    """取得時刻
    （過去データから取得した場合は、過去データが記録されているファイル名から取得した日付）
    """
    retr_dt = Column(DateTime, nullable=False, default=datetime.datetime.now())

    """災害情報文字列が保存されていた位置
    """
    text_pos = Column(sqlalchemy.Enum(TextPosition), nullable=False)

    """災害情報の通知状態
    """
    notify_status = Column(
        sqlalchemy.Enum(NotifyStatus), nullable=False, default=NotifyStatus.NOT_YET
    )

    """詳細テーブルのオブジェクト
    """
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
