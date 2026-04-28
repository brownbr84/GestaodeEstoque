import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()

if DB_TYPE == "postgres":
    user = os.getenv("PG_USER", "postgres")
    password = os.getenv("PG_PASSWORD", "tracebox_password")
    host = os.getenv("PG_HOST", "db")
    port = os.getenv("PG_PORT", "5432")
    db_name = os.getenv("PG_DATABASE", "tracebox_db")
    DATABASE_URL = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"
    engine = create_engine(DATABASE_URL, echo=False)
else:
    _db_file = os.getenv("SQLITE_PATH", "estoque_ferramentas.db")
    _base_dir   = os.path.dirname(os.path.abspath(__file__))  # database/
    _tracebox_dir = os.path.dirname(_base_dir)                # tracebox/
    _root_dir   = os.path.dirname(_tracebox_dir)              # project root
    _path_root  = os.path.join(_root_dir, _db_file)
    _path_local = os.path.join(_tracebox_dir, _db_file)
    DB_PATH = _path_root if os.path.exists(_path_root) else _path_local
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_session():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()