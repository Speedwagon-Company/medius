from web3 import Web3, AsyncWeb3, WebSocketProvider,AsyncHTTPProvider
import os, asyncio
from websockets.exceptions import ConnectionClosedError
import requests, asyncio
from web3.exceptions import TransactionNotFound
import websockets
from typing import Any


RECIPIENT = "0x676320A4F2ccD0D6A8a56C0Ebf2AF1aa984A12fD"
TRANSACTIONS = {}

# Сумма для отправки (в ETH, конвертируется в Wei)
AMOUNT_ETH = 0.001


W3: AsyncWeb3 = None


# Проверяем соединение
async def init_w3():
    global W3
    PRIVATE_KEY = os.getenv("PRIVATE_WALLET_KEY")
    RPC_URL = os.getenv("RPC_URL")
    W3 = AsyncWeb3(AsyncHTTPProvider(RPC_URL))

    if not await W3.is_connected():
        print("❌ Не удалось подключиться к Chainstack ноде")
        print("Проверь RPC URL и интернет соединение")
        exit(1)

    print(f"Подключено к сети: {await W3.eth.chain_id}")
    print(f"Баланс ноды: {await W3.eth.get_balance(W3.eth.account.from_key(PRIVATE_KEY).address)} Wei")

# TODO: refactor, source: https://docs.chainstack.com/docs/monitoring-transaction-propagation-from-node-to-mempool-in-evm-networks-with-python  
async def subscribe_to_blocks():
    print(os.getenv("CHAINSTACK_WS"))
    while True:  
        try:
            k_args =  {
                'ping_interval': 30,  
                'ping_timeout': 10    
            }
            async with AsyncWeb3(WebSocketProvider(os.getenv("CHAINSTACK_WS"),websocket_kwargs=k_args)) as w3:
                MY_ADDRESS = os.getenv("OWNER_WALLET")
                
                sub_id = await w3.eth.subscribe("newPendingTransactions")
                print(f"Подписка создана: {sub_id}")
                
                try:
                    async for message in w3.socket.process_subscriptions():
                        tx_hash = message.get("result")  
                        
                        if tx_hash:
                            try:
                                tx = await w3.eth.get_transaction(tx_hash)
                                
                                if tx and tx.get("to") and tx["to"].lower() == MY_ADDRESS.lower():
                                    amount_eth = w3.from_wei(tx["value"], "ether")
                                    print(f"Входящий платеж от {tx['from']}: {amount_eth} ETH")
                                    print(f"   Хэш: {tx_hash.hex() if hasattr(tx_hash, 'hex') else tx_hash}")
                                    TRANSACTIONS[tx["from"]] = tx
                            except Exception as e:
                                print(f"Ошибка при получении транзакции: {e}")
                                
                except (ConnectionResetError, ConnectionClosedError) as e:
                    print(f"Соединение разорвано: {e}")
                    raise  
                    
        except (ConnectionResetError, ConnectionClosedError, Exception) as e:
            data = {
            "content": f"Crypto module crashed {e}",
            }

            await asyncio.to_thread(requests.post, os.getenv("WEBHOOK_URL"), json=data)
            print(f"Ошибка подключения: {e}")
            print("Переподключение через 2 секунд...")
            await asyncio.sleep(2)
            continue


async def handle_pending_transactions():
    WALLET_TO_WATCH = Web3.to_checksum_address("0x676320A4F2ccD0D6A8a56C0Ebf2AF1aa984A12fD")
    
    ws_url = os.getenv("CHAINSTACK_WS")
    http_url = ws_url.replace("wss://", "https://") if ws_url else None
    
    if not http_url:
        print("Ошибка: CHAINSTACK_WS не задан")
        return
    
    global W3
    
    if not await W3.is_connected():
        print(f"Не удалось подключиться к узлу: {http_url}")
        return
    
    print(f"Подключено к узлу")

    last_block = await W3.eth.block_number
    print(f"Текущий блок: {last_block}")
    
    while True:
        try:
            current_block = await W3.eth.block_number
            
            if current_block > last_block:
                print(f"Новые блоки: {last_block + 1} -> {current_block}")
                

                for block_num in range(last_block + 1, current_block + 1):
                    try:
                        block = await W3.eth.get_block(block_num, full_transactions=True)
                        
                        for tx in block.transactions:
                            from_addr = tx['from'].lower()
                            to_addr = tx['to'].lower() if tx.get('to') else None
                            target = WALLET_TO_WATCH.lower()

                            if from_addr == target or (to_addr and to_addr == target):
                                direction = "📤 ИСХОДЯЩАЯ" if from_addr == target else "📥 ВХОДЯЩАЯ"
                                value_eth = W3.from_wei(tx['value'], 'ether')
                                TRANSACTIONS[tx["from"]] = tx
                                print(f"\n🔔 Найдена {direction} транзакция в блоке {block_num}!")
                                print(f"Хэш: {tx.hash.hex()}")
                                print(f"От: {tx['from']}")
                                print(f"Кому: {tx['to']}")
                                print(f"Value: {value_eth} ETH")
                                print("-" * 50)
                                
                    except Exception as e:
                        print(f"Ошибка в блоке {block_num}: {e}")
                
                last_block = current_block
            

            await asyncio.sleep(12)
            
        except Exception as e:
            print(f" Ошибка: {e}")
            await asyncio.sleep(1)


async def context_manager_subscription_example():
    ws_url = os.getenv("CHAINSTACK_WS")
    if not ws_url:
        print("[crypto] CHAINSTACK_WS is not set, subscription loop is disabled")
        return

    k_args = {"ping_interval": 30, "ping_timeout": 10}
    target_wallet = (os.getenv("OWNER_WALLET") or RECIPIENT).lower()
    reconnect_delay = 1
    max_reconnect_delay = 30

    while True:
        try:
            async with AsyncWeb3(WebSocketProvider(ws_url, websocket_kwargs=k_args)) as w3:
                subscription_id = await w3.eth.subscribe("newPendingTransactions", True)
                print("[crypto] pending transactions subscription started")
                reconnect_delay = 1

                try:
                    async for response in w3.socket.process_subscriptions():
                        _handle_pending_subscription_message(response, target_wallet)
                finally:
                    try:
                        await w3.eth.unsubscribe(subscription_id)
                    except Exception as unsub_error:
                        print(f"[crypto] failed to unsubscribe pending transactions: {unsub_error}")
        except asyncio.CancelledError:
            print("[crypto] pending transactions subscription cancelled")
            raise
        except (ConnectionClosedError, ConnectionResetError, OSError, websockets.ConnectionClosed) as conn_error:
            print(
                f"[crypto] websocket connection lost ({type(conn_error).__name__}), "
                f"retrying in {reconnect_delay}s"
            )
        except Exception as error:
            print(
                f"[crypto] subscription error ({type(error).__name__}), "
                f"retrying in {reconnect_delay}s: {error}"
            )

        await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)


def _handle_pending_subscription_message(response: Any, target_wallet: str) -> None:
    result = response.get("result") if isinstance(response, dict) else None
    if not isinstance(result, dict):
        return

    tx_to = result.get("to")
    tx_from = result.get("from")
    if not isinstance(tx_to, str) or not isinstance(tx_from, str):
        return

    if tx_to.lower() != target_wallet:
        return

    tx_hash_key = _normalize_tx_hash(result.get("hash"))
    if tx_hash_key:
        TRANSACTIONS[tx_hash_key] = result
    tx_hash = result.get("hash")
    printable_hash = tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)
    print(f"[crypto] matched pending transaction {printable_hash}")

def _normalize_wallet(address: str | None) -> str:
    if not isinstance(address, str):
        return ""
    return address.strip().lower()

def _normalize_tx_hash(tx_hash: Any) -> str:
    if tx_hash is None:
        return ""
    if hasattr(tx_hash, "hex"):
        return tx_hash.hex().strip().lower()
    return str(tx_hash).strip().lower()

def _transaction_matches(
    tx: dict[str, Any],
    sender_wallet: str,
    recipient_wallet: str,
    min_value_wei: int,
) -> bool:
    tx_from = _normalize_wallet(tx.get("from"))
    tx_to = _normalize_wallet(tx.get("to"))
    tx_value = tx.get("value")
    if not isinstance(tx_value, int):
        return False

    return (
        tx_from == _normalize_wallet(sender_wallet)
        and tx_to == _normalize_wallet(recipient_wallet)
        and tx_value >= min_value_wei
    )

async def _scan_recent_blocks_for_match(
    sender_wallet: str,
    recipient_wallet: str,
    min_value_wei: int,
    lookback_blocks: int = 6,
):
    if W3 is None:
        return None

    latest_block = await W3.eth.block_number
    start_block = max(0, latest_block - lookback_blocks)
    for block_num in range(latest_block, start_block - 1, -1):
        block = await W3.eth.get_block(block_num, full_transactions=True)
        for tx in block.get("transactions", []):
            if _transaction_matches(tx, sender_wallet, recipient_wallet, min_value_wei):
                tx_hash_key = _normalize_tx_hash(tx.get("hash"))
                if tx_hash_key:
                    TRANSACTIONS.pop(tx_hash_key, None)
                return tx
    return None

def check_pending_transaction(tx_hash, target_address_lower, w3):
  try:
    tx = w3.eth.get_transaction(tx_hash)
    if tx['from'].lower() == target_address_lower or (
        tx['to'] and tx['to'].lower() == target_address_lower):
      return tx
  except TransactionNotFound:
    pass
  return None


async def wait_for_transaction(sender_wallet: str, recipient_wallet: str, min_value_wei: int):
    print("STARTED CHECKING")
    attempts = 0
    while True:
        for tx_hash_key, tx in list(TRANSACTIONS.items()):
            if _transaction_matches(tx, sender_wallet, recipient_wallet, min_value_wei):
                print("GOT TRANSaCTION")
                TRANSACTIONS.pop(tx_hash_key, None)
                return tx

        if attempts % 5 == 0:
            try:
                from_chain = await _scan_recent_blocks_for_match(
                    sender_wallet=sender_wallet,
                    recipient_wallet=recipient_wallet,
                    min_value_wei=min_value_wei,
                )
                if from_chain:
                    print("GOT TRANSACTION FROM RECENT BLOCKS")
                    return from_chain
            except Exception as scan_error:
                print(f"[crypto] failed to scan recent blocks: {scan_error}")

        attempts += 1
        await asyncio.sleep(1)




async def sign_and_send(amount: float, to: str):
    print("start sign", amount, to, type(to))
    
    account = W3.eth.account.from_key(os.getenv("PRIVATE_WALLET_KEY"))
    print("ACC", account.address)
    
    gas_estimate = await W3.eth.estimate_gas({
        'from': account.address,
        'to': to,
        'value': W3.to_wei(amount, 'ether')  
    })
    
    gas_price = await W3.eth.gas_price
    if gas_price is None:
        gas_price = await W3.to_wei('20', 'gwei')
    
    nonce = await W3.eth.get_transaction_count(account.address)
    print("Nonce", nonce)
    
    chain_id = await W3.eth.chain_id
    if chain_id is None:
        chain_id = 1
    
    tx = {
        'nonce': nonce,
        'to': to,
        'value': W3.to_wei(amount, 'ether'),
        'gas': gas_estimate,
        'gasPrice': gas_price,
        'chainId': chain_id
    }
    print("SENDING", tx)
    
    signed_tx = account.sign_transaction(tx)
    
    tx_hash = await W3.eth.send_raw_transaction(signed_tx.raw_transaction)
    
    return tx_hash
