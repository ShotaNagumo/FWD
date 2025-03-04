import datetime
from enum import Enum, auto

import sqlalchemy
import util_db_manager
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

Base = sqlalchemy.orm.declarative_base()


def create_table_all():
    Base.metadata.create_all(bind=util_db_manager.ENGINE)


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

    """応援
    """
    応援 = auto()

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

    """終了
    """
    終了 = auto()


class NoticeType(Enum):
    """案内情報種別

    Args:
        Enum (_type_): Enum基底クラス
    """

    """一般案内
    """
    一般案内 = auto()

    """鎮火情報
    """
    鎮火情報 = auto()


class NiigataNoticeText(Base):
    """「発生」「終了」以外の情報（:=案内情報）を格納するテーブル
    1. 鎮火情報
    2. ページ上部に表示される案内
       （訓練、障害、緊援隊派遣等の情報）
    """

    """テーブル名
    """
    __tablename__ = "niigata_notice_text"

    """NiigataInfoText ID
    """
    id = Column(Integer, primary_key=True, autoincrement=True)

    """案内情報種別
    """
    notice_type = Column(sqlalchemy.Enum(NoticeType), nullable=False)

    """案内情報文字列
    """
    raw_text = Column(String, nullable=False)

    """取得時刻
    （過去データから取得した場合は、過去データが記録されているファイル名から取得した日付）
    """
    retr_dt = Column(DateTime, nullable=False, default=datetime.datetime.now())

    """案内情報の通知状態
    """
    notify_status = Column(
        sqlalchemy.Enum(NotifyStatus), nullable=False, default=NotifyStatus.NOT_YET
    )


class NiigataRawText(Base):
    """災害情報を格納するテーブル"""

    """テーブル名
    """
    __tablename__ = "niigata_raw_text"

    """NiigataRawText ID
    """
    id = Column(Integer, primary_key=True, autoincrement=True)

    """災害情報文字列
    """
    raw_text = Column(String, nullable=False)

    """取得時刻
    （過去データから取得した場合は、過去データが記録されているファイル名から取得した日付）
    """
    retr_dt = Column(DateTime, nullable=False, default=datetime.datetime.now())

    """災害情報の通知状態
    """
    notify_status = Column(
        sqlalchemy.Enum(NotifyStatus), nullable=False, default=NotifyStatus.NOT_YET
    )

    """詳細テーブルのオブジェクト
    """
    detail_info = relationship("NiigataDisasterDetail", uselist=False)


class NiigataDisasterDetail(Base):
    __tablename__ = "niigata_disaster_detail"

    """ "niigata_raw_text"テーブルのID
    """
    raw_text_id = Column(
        Integer, ForeignKey("niigata_raw_text.id", ondelete="CASCADE"), primary_key=True
    )
    """災害種別
    """
    main_category = Column(sqlalchemy.Enum(DisasterMainCategory), nullable=False)
    """災害発生時刻
    """
    open_dt = Column(DateTime, nullable=False)
    """災害終了時刻
    """
    close_dt = Column(DateTime, nullable=True)
    """災害状態
    """
    status = Column(sqlalchemy.Enum(DisasterStatus), nullable=False)
    """住所1（区名/道路名）
    """
    address1 = Column(String, nullable=False)
    """住所2（町名/道路方向）
    """
    address2 = Column(String, nullable=False)
    """住所3（丁目/キロポスト、道路施設）
    """
    address3 = Column(String, nullable=True)
