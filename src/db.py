import os
from tortoise import Tortoise, fields
from tortoise.models import Model
from typing import Optional, List
from datetime import datetime


class User(Model):
    id = fields.IntField(pk=True)
    discord_id = fields.BigIntField(unique=True, description="ID пользователя в Discord")
    created_at = fields.DatetimeField(auto_now_add=True, description="Дата регистрации")
    
    class Meta:
        table = "users"
    
    def __str__(self):
        return f"User {self.discord_id}"

class Transaction(Model):
    id = fields.IntField(pk=True)
    
    sender = fields.ForeignKeyField("models.User", related_name="sent_transactions", null=True)
    receiver = fields.ForeignKeyField("models.User", related_name="received_transactions", null=True)
    
    sender_wallet = fields.CharField(max_length=100)
    receiver_wallet = fields.CharField(max_length=100)
    channel_id = fields.IntField()
    
    payment_status = fields.CharField(max_length=20, default="pending")
    transaction_hash = fields.CharField(max_length=255, unique=True, null=True)
    amount = fields.DecimalField(max_digits=20, decimal_places=8, null=True)
    currency = fields.CharField(max_length=10, default="USDT")

    created_at = fields.DatetimeField(auto_now_add=True, description="Дата создания")
    updated_at = fields.DatetimeField(auto_now=True, description="Дата обновления")

    
    class Meta:
        table = "transactions"


async def init_db(db_url: str = None):
    if not db_url:
        db_url = 'sqlite://bot.db'

    os.environ['TZ'] = 'UTC'
    
    await Tortoise.init(
        db_url=db_url,
        modules={'models': ['db']},
        use_tz=True,
        timezone='UTC',
    )
    
    await Tortoise.generate_schemas()
    print(f"[DB] Инициализирована БД: {db_url}")
async def close_db():
    await Tortoise.close_connections()
    print("[DB] Соединение закрыто")


async def get_or_create_user(discord_id: int) -> User:
    user, created = await User.get_or_create(
        discord_id=discord_id
    )

    return user

async def get_user(discord_id: int) -> Optional[User]:
    return await User.filter(discord_id=discord_id).first()

async def delete_user(discord_id: int) -> bool:
    user = await get_user(discord_id)
    if user:
        await user.delete()
        return True
    return False

async def create_transaction(
    sender_wallet: str,
    receiver_wallet: str,
    amount: float = None,
    sender_discord_id: int = None,
    receiver_discord_id: int = None,
    currency: str = "USDT",
    chan_id: int = None
) -> Transaction:

    sender_user = None
    receiver_user = None
    
    if sender_discord_id:
        sender_user = await get_or_create_user(sender_discord_id)
    
    if receiver_discord_id:
        receiver_user = await get_or_create_user(receiver_discord_id)
    
    transaction = await Transaction.create(
        sender=sender_user,
        receiver=receiver_user,
        sender_wallet=sender_wallet,
        receiver_wallet=receiver_wallet,
        amount=amount,
        currency=currency,
        payment_status="pending",
        channel_id=chan_id
    )
    
    print(f"[DB] Создана транзакция #{transaction.id}: {sender_wallet} -> {receiver_wallet}")
    return transaction

async def update_transaction_status(
    transaction_id: int, 
    status: str,
    transaction_hash: str = None
) -> Optional[Transaction]:
    transaction = await Transaction.filter(id=transaction_id).first()
    if not transaction:
        return None
    
    transaction.payment_status = status
    
    if transaction_hash:
        transaction.transaction_hash = transaction_hash
    
    await transaction.save()
    return transaction

async def get_transaction(transaction_id: int) -> Optional[Transaction]:
    return await Transaction.filter(id=transaction_id).first()

async def get_user_transactions(
    discord_id: int,
    status: str = None,
    limit: int = 50
) -> List[Transaction]:
    user = await get_user(discord_id)
    if not user:
        return []
    
    query = Transaction.filter(
        fields.Q(sender=user) | fields.Q(receiver=user)
    )
    
    if status:
        query = query.filter(payment_status=status)
    
    return await query.order_by("-created_at").limit(limit).prefetch_related("sender", "receiver")

async def get_user_sent_transactions(discord_id: int, limit: int = 50) -> List[Transaction]:
    user = await get_user(discord_id)
    if not user:
        return []
    
    return await Transaction.filter(sender=user).order_by("-created_at").limit(limit).prefetch_related("receiver")

async def get_user_received_transactions(discord_id: int, limit: int = 50) -> List[Transaction]:
    user = await get_user(discord_id)
    if not user:
        return []
    
    return await Transaction.filter(receiver=user).order_by("-created_at").limit(limit).prefetch_related("sender")

async def get_transactions_by_wallet(
    wallet_address: str,
    status: str = None,
    limit: int = 50
) -> List[Transaction]:
    query = Transaction.filter(
        fields.Q(sender_wallet=wallet_address) | fields.Q(receiver_wallet=wallet_address)
    )
    
    if status:
        query = query.filter(payment_status=status)
    
    return await query.order_by("-created_at").limit(limit).prefetch_related("sender", "receiver")

async def get_pending_transactions(limit: int = 100) -> List[Transaction]:
    return await Transaction.filter(payment_status="pending").order_by("created_at").limit(limit).prefetch_related("sender", "receiver")

async def cancel_transaction(transaction_id: int) -> bool:
    transaction = await get_transaction(transaction_id)
    if not transaction or transaction.payment_status != "pending":
        return False
    
    transaction.payment_status = "cancelled"
    await transaction.save()
    print(f"[DB] Транзакция #{transaction_id} отменена")
    return True




"""
async def test():
    await init_db()
    
    # Создаем пользователей
    user1 = await get_or_create_user(123456789)
    user2 = await get_or_create_user(987654321)
    
    # Создаем транзакцию
    tx = await create_transaction(
        sender_wallet="0x123...abc",
        receiver_wallet="0x456...def",
        amount=100.5,
        sender_discord_id=123456789,
        receiver_discord_id=987654321,
        currency="USDT"
    )
    print(f"Создана транзакция: {tx}")
    
    # Обновляем статус
    await update_transaction_status(tx.id, "completed", "0xhash123...")
    
    # Получаем транзакции пользователя
    user_txs = await get_user_transactions(123456789)
    print(f"Транзакции пользователя: {len(user_txs)}")
    
    for tx in user_txs:
        print(f"  #{tx.id}: {tx.sender_wallet} -> {tx.receiver_wallet} [{tx.payment_status}]")
    
    # Статистика
    stats = await get_statistics()
    print(f"Статистика: {stats}")
    
    await close_db()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test())
"""