from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy ORM 基类（Wave 1+ 模型继承；Alembic autogenerate 用）。"""
