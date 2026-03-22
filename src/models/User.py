from sqlalchemy import create_engine, String, ForeignKey, Column, Date, Integer, Numeric
from sqlalchemy.orm import declarative_base, sessionmaker, Mapped, mapped_column, relationship


Base = declarative_base()

from sqlalchemy import Column, Integer, String, Date, Numeric
from sqlalchemy.ext.declarative import declarative_base
from datetime import date

# Импортируем Base из вашего db.py
from db import Base

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)

    def __repr__(self):
        return f"<User(name='{self.name}', id={self.id})>"