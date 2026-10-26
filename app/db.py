from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def init_db():
    # These extensions must exist in the PostgreSQL image. pgvector stores embeddings;
    # pg_textsearch provides the BM25 operator and index access method.
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_textsearch"))

    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # One BM25 expression index covers the text fields used for lexical job matching.
    # Keep this expression in sync with the expression in app.services.search.
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS jobs_search_text_bm25_idx
            ON jobs USING bm25 (
                (COALESCE(position, '') || ' ' || COALESCE(company, '') || ' ' ||
                 COALESCE(location, '') || ' ' || COALESCE(description, ''))
            ) WITH (text_config='english')
        """))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
