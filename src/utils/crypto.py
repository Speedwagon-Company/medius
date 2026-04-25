from web3 import Web3, AsyncWeb3, WebSocketProvider
import os, asyncio
from websockets.exceptions import ConnectionClosedError
import requests, asyncio
from web3.exceptions import TransactionNotFound
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading, json, time, websockets


RECIPIENT = "0x676320A4F2ccD0D6A8a56C0Ebf2AF1aa984A12fD"
TRANSACTIONS = {}

# Сумма для отправки (в ETH, конвертируется в Wei)
AMOUNT_ETH = 0.001


W3: Web3 = None


# Проверяем соединение
def init_w3():
    global W3
    PRIVATE_KEY = os.getenv("PRIVATE_WALLET_KEY")
    RPC_URL = os.getenv("RPC_URL")
    W3 = Web3(Web3.HTTPProvider(RPC_URL))

    if not W3.is_connected():
        print("❌ Не удалось подключиться к Chainstack ноде")
        print("Проверь RPC URL и интернет соединение")
        exit(1)

    print(f"Подключено к сети: {W3.eth.chain_id}")
    print(f"Баланс ноды: {W3.eth.get_balance(W3.eth.account.from_key(PRIVATE_KEY).address)} Wei")

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

            response = requests.post(os.getenv("WEBHOOK_URL"), json=data)
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
    
    if not W3.is_connected():
        print(f"Не удалось подключиться к узлу: {http_url}")
        return
    
    print(f"Подключено к узлу")

    last_block = W3.eth.block_number
    print(f"Текущий блок: {last_block}")
    
    while True:
        try:
            current_block = W3.eth.block_number
            
            if current_block > last_block:
                print(f"Новые блоки: {last_block + 1} -> {current_block}")
                

                for block_num in range(last_block + 1, current_block + 1):
                    try:
                        block = W3.eth.get_block(block_num, full_transactions=True)
                        
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


def check_pending_transaction(tx_hash, target_address_lower, w3):
  try:
    tx = w3.eth.get_transaction(tx_hash)
    if tx['from'].lower() == target_address_lower or (
        tx['to'] and tx['to'].lower() == target_address_lower):
      return tx
  except TransactionNotFound:
    pass
  return None


async def wait_for_transaction(tx_hash):
    print("STARTED CHECKING")
    while True:
        if TRANSACTIONS.get(tx_hash):
            print("GOT TRANSaCTION")
            return TRANSACTIONS[tx_hash]
        await asyncio.sleep(1)




def sign_and_send(amount, to): 
    print("start sign", amount, to, type(to))
    global W3
    account = W3.eth.account.from_key(os.getenv("PRIVATE_WALLET_KEY"))
    print("ACC", account)
    gas_estimate = W3.eth.estimate_gas({
    'from': account.address,
    'to': to,
    'value': W3.to_wei(0.001, 'ether')
    })

    gas_price = W3.eth.generate_gas_price()
    nonce = W3.eth.get_transaction_count(account.address)
    print("Nonce", nonce)
    
    gas_price = W3.eth.gas_price
    if gas_price is None:
        gas_price = W3.to_wei('20', 'gwei')
    
    chain_id = W3.eth.chain_id
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
    tx_hash = W3.eth.send_raw_transaction(signed_tx.raw_transaction) 
    return tx_hash

