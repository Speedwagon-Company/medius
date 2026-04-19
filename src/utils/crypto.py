from web3 import Web3, AsyncWeb3, WebSocketProvider
import os, asyncio
from websockets.exceptions import ConnectionClosedError


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

async def subscribe_to_blocks():
    print(os.getenv("CHAINSTACK_WS"))
    while True:  # Добавляем цикл для переподключения
        try:
            async with AsyncWeb3(WebSocketProvider(os.getenv("CHAINSTACK_WS"))) as w3:
                MY_ADDRESS = os.getenv("OWNER_WALLET")
                
                sub_id = await w3.eth.subscribe("newPendingTransactions")
                print(f"Подписка создана: {sub_id}")
                
                # heartbeat_task = asyncio.create_task(send_heartbeat(w3))
                
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
            print(f"Ошибка подключения: {e}")
            print("Переподключение через 2 секунд...")
            await asyncio.sleep(2)
            continue
                
async def wait_for_transaction(address):
    print("STARTED CHECKING")
    while True:
        # print(f"CHECING {address} {TRANSACTIONS.get(address)}")
        if TRANSACTIONS.get(address):
            print("GOT TRANSaCTION")
            return TRANSACTIONS[address]
        await asyncio.sleep(1)

async def send_heartbeat(w3):
    while True:
        try:
            await asyncio.sleep(10)
            if hasattr(w3, 'socket') and w3.socket:
                # Правильный способ отправки через WebSocket
                await w3.socket.send('ping', None)  # или ('ping', [])
                print("💓 Heartbeat отправлен")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Heartbeat ошибка: {e}")
            break





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

# tx_hash = sign_and_send(tx)
# print(f"✅ Транзакция отправлена!")
# print(f"📝 Хэш транзакции: {tx_hash.hex()}")

# # Ждем подтверждения (опционально, но полезно)
# print("⏳ Ожидание подтверждения...")
# receipt = W3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

# if receipt['status'] == 1:
#     print("✅ Транзакция успешно подтверждена!")
#     print(f"🔗 Блок: {receipt['blockNumber']}")
#     print(f"💰 Газ использовано: {receipt['gasUsed']}")
# else:
#     print("❌ Транзакция не удалась!")