import sqlalchemy
import util_db_manager
from sqlalchemy import Column, Integer

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
