from contextlib import contextmanager
from typing import Final

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from fwdutil import config

# データベースファイルパスを決定
variable_dir = config.get_variable_dir()
db_filepath = variable_dir / "database" / "fwd.db"
db_filepath.parent.mkdir(exist_ok=True)

# Engine, Session設定
UB_URL: Final[str] = f"sqlite:///{db_filepath.as_posix()}"
ENGINE = create_engine(UB_URL, echo=True)
SESSION = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)


# sessionを取得する関数
@contextmanager
def session_factory():
    session = SESSION()
    try:
        yield session
        session.commit()
    except IntegrityError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise


# sqlite 外部キー制約を強制するpragma
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON ")
    cursor.close()
