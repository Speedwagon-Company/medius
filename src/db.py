from typing import Any

from sqlalchemy import Boolean, JSON, UniqueConstraint, String, ForeignKey, select, func, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import mapped_column, Mapped, relationship, Session
from sqlalchemy.exc import IntegrityError
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
    __table_args__ = (
        UniqueConstraint("hash", name="uq_transactions_hash"),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True)
    trade_id: Mapped[int | None] = mapped_column(ForeignKey("trades.id"), nullable=True, index=True)
    reciever_id: Mapped[int] = mapped_column(ForeignKey("users.discord_id"))
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.discord_id"))
    channel_id: Mapped[int | None] = mapped_column(nullable=True, index=True)

    reciever_wallet: Mapped[str] = mapped_column()
    sender_wallet: Mapped[str] = mapped_column()
    escrow_wallet: Mapped[str | None] = mapped_column(nullable=True)
    expected_amount: Mapped[float | None] = mapped_column(nullable=True)

    recieved: Mapped[float] = mapped_column()

    hash: Mapped[str] = mapped_column(nullable=True)
    network: Mapped[str] = mapped_column(nullable=True)
    coin: Mapped[str] = mapped_column(nullable=False)

    status: Mapped[str] = mapped_column(default="WAITING_DEPOSIT")

    trade: Mapped["Trade"] = relationship()
    reciever: Mapped["User"] = relationship(foreign_keys=[reciever_id])
    sender: Mapped["User"] = relationship(foreign_keys=[sender_id])

class Config(Base):
    __tablename__ = "configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    embed_suc_color: Mapped[str] = mapped_column()

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

async def ensure_config_exists() -> None:
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(Config).limit(1))
        config = result.scalar_one_or_none()
        if config is None:
            session.add(Config(embed_suc_color="#00ff00"))
            await session.commit()

async def get_embed_suc_color() -> str:
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(Config.embed_suc_color).limit(1))
        color = result.scalar_one_or_none()
        if color is None:
            await ensure_config_exists()
            return "#00ff00"
        return color

async def set_embed_suc_color(new_color: str) -> None:
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(Config.id).limit(1))
        config_id = result.scalar_one_or_none()
        if config_id is None:
            await ensure_config_exists()
            await session.execute(update(Config).values(embed_suc_color=new_color))
        else:
            await session.execute(
                update(Config)
                .where(Config.id == config_id)
                .values(embed_suc_color=new_color)
            )
        await session.commit()

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
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise
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

async def get_transaction(transaction_id: int):
    async with AsyncSessionFactory() as session:
        return await session.get(Transaction, transaction_id)

async def list_transactions_by_statuses(statuses: list[str]):
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(Transaction).where(Transaction.status.in_(statuses))
        )
        return list(result.scalars().all())

async def try_update_transaction_status(transaction_id: int, from_status: str, to_status: str) -> bool:
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            update(Transaction)
            .where(
                Transaction.id == transaction_id,
                Transaction.status == from_status,
            )
            .values(status=to_status)
        )
        await session.commit()
        return result.rowcount == 1

async def attach_deposit_if_waiting(transaction_id: int, tx_hash: str, recieved: float) -> bool:
    normalized_hash = tx_hash.strip().lower()
    async with AsyncSessionFactory() as session:
        try:
            result = await session.execute(
                update(Transaction)
                .where(
                    Transaction.id == transaction_id,
                    Transaction.status == "WAITING_DEPOSIT",
                    Transaction.hash.is_(None),
                )
                .values(
                    hash=normalized_hash,
                    recieved=recieved,
                    status="DEPOSIT_SEEN",
                )
            )
            await session.commit()
            if result.rowcount == 1:
                return True
        except IntegrityError:
            await session.rollback()
            return False

        current = await session.get(Transaction, transaction_id)
        if not current or not current.hash:
            return False
        return current.hash.strip().lower() == normalized_hash

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
