from typing import Any

from sqlalchemy import Boolean, JSON, UniqueConstraint, create_engine, String, ForeignKey, Column, Date, Integer, Numeric, select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, mapped_column, Mapped, relationship, Session
from exceptions import EntityNotFoundError


engine = create_async_engine(
    "sqlite+aiosqlite:///bot.db"
)


AsyncSessionFactory = async_sessionmaker(
    engine, 
    class_=AsyncSession,
    expire_on_commit=False
)
session: Session = AsyncSessionFactory
Base = declarative_base()

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        



class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    discord_id: Mapped[int] = mapped_column(unique=True)


class Trade(Base):
    __tablename__ = "trades"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user1_id: Mapped[int] = mapped_column(ForeignKey("users.discord_id"))
    user2_id: Mapped[int] = mapped_column(ForeignKey("users.discord_id"))
    
    user1: Mapped["User"] = relationship(foreign_keys=[user1_id])
    user2: Mapped["User"] = relationship(foreign_keys=[user2_id])

class Transaction(Base):
    __tablename__ = "transactions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    reciever_id: Mapped[int] = mapped_column(ForeignKey("users.discord_id"))
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.discord_id"))

    reciever_wallet: Mapped[str] = mapped_column()
    sender_wallet: Mapped[str] = mapped_column()

    recieved: Mapped[float] = mapped_column()

    hash: Mapped[str] = mapped_column(nullable=True)
    network: Mapped[str] = mapped_column(nullable=True)
    coin: Mapped[str] = mapped_column(nullable=False)

    status: Mapped[str] = mapped_column(default="WAITING")

    reciever: Mapped["User"] = relationship(foreign_keys=[reciever_id])
    sender: Mapped["User"] = relationship(foreign_keys=[sender_id])

class CommandSetting(Base):
    __tablename__ = "command_settings"
    __table_args__ = (
        UniqueConstraint("guild_id", "command_name", name="uq_command_settings_guild_command"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int] = mapped_column(index=True)
    command_name: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extra_settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

async def create_trade(user1_discord_id: int, user2_discord_id: int):
    async with AsyncSessionFactory() as session:
        trade = Trade(user1_id=user1_discord_id, user2_id=user2_discord_id)
        session.add(trade)
        await session.commit()
        return trade
    
async def create_transaction(**kwargs):
    async with AsyncSessionFactory() as session:
        trans = Transaction(**kwargs)
        session.add(trans)
        await session.commit()
        await session.refresh(trans)
        return trans
    
async def update_transaction_status(transaction_id, new_status):
    async with AsyncSessionFactory() as session:
        trans = await session.get(Transaction, transaction_id)
        if not trans:
            raise EntityNotFoundError(f"transaction with id {transaction_id} not found")
        
        trans.status = new_status
        await session.commit()
        return trans
    
async def update_transaction(transaction_id, **kwargs):
    async with AsyncSession() as session:
        trans = await session.get(Transaction, transaction_id)
        if not trans:
            raise EntityNotFoundError(f"transaction with id {transaction_id} not found")
        
        for key, value in kwargs.items():
            if hasattr(trans, key):
                setattr(trans, key, value)
        
        session.add(trans)
        await session.commit()
        await session.refresh(trans)  
        
        return trans

async def get_transaction_by_hash(tx_hash: str):
    normalized_hash = tx_hash.strip().lower()
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(Transaction).where(func.lower(Transaction.hash) == normalized_hash)
        )
        return result.scalar_one_or_none()

async def get_command_setting(guild_id: int, command_name: str):
    normalized_name = command_name.strip().lower()
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(CommandSetting).where(
                CommandSetting.guild_id == guild_id,
                CommandSetting.command_name == normalized_name,
            )
        )
        return result.scalar_one_or_none()

async def upsert_command_setting(
    guild_id: int,
    command_name: str,
    enabled: bool,
    extra_settings: dict[str, Any] | None = None,
):
    normalized_name = command_name.strip().lower()
    payload = extra_settings or {}

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(CommandSetting).where(
                CommandSetting.guild_id == guild_id,
                CommandSetting.command_name == normalized_name,
            )
        )
        setting = result.scalar_one_or_none()

        if setting is None:
            setting = CommandSetting(
                guild_id=guild_id,
                command_name=normalized_name,
                enabled=enabled,
                extra_settings=payload,
            )
            session.add(setting)
        else:
            setting.enabled = enabled
            setting.extra_settings = payload

        await session.commit()
        await session.refresh(setting)
        return setting
