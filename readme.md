создать свой .env файл на основе .env.example и заполнить его

скачать бублики
pip install -r requirements.txt

запустить прожект
python src/main.py 

## Trade flow guard migration runbook

- При старте бот сначала выполняет `db.init_db()`, затем `migrate_trade_flow_guard`.
- Миграция идемпотентна: её можно запускать повторно.
- Ручной запуск миграции:
  - `python migrate_trade_flow_guard.py`

### Что делает миграция

- Добавляет колонки `trade_id`, `channel_id`, `escrow_wallet`, `expected_amount` (если их нет).
- Нормализует старые статусы `NULL`, `''`, `WAITING` в `WAITING_DEPOSIT`.
- Создаёт индексы `ix_transactions_trade_id`, `ix_transactions_channel_id`.
- Создаёт уникальный partial index `uq_transactions_hash` только для `hash IS NOT NULL`.

### Legacy duplicate tx hash

- Если в legacy-данных есть дубликаты non-null `hash`, миграция падает fail-fast с `DuplicateTransactionHashError`.
- Это сделано специально, чтобы не терять финансовую историю автоматически.
- Перед повторным запуском миграции устраните дубликаты вручную.
- Диагностика:
  - `SELECT lower(trim(hash)) AS hash, COUNT(*) FROM transactions WHERE hash IS NOT NULL AND trim(hash) <> '' GROUP BY lower(trim(hash)) HAVING COUNT(*) > 1;`

## RELEASING recovery runbook

- После рестарта бот не делает auto-resend для зависших `RELEASING`.
- Такие сделки переводятся в `NEEDS_RECONCILIATION` и требуют ручной проверки.
- Проверка кандидатов:
  - `SELECT id, hash, status, reciever_wallet, sender_wallet, recieved FROM transactions WHERE status = 'NEEDS_RECONCILIATION';`
- Ручное восстановление:
  1. Проверить payout on-chain.
  2. Если payout подтверждён: обновить статус в `RELEASED` или `CANCELED`.
  3. Если payout не был отправлен/подтверждён: перевести в `FAILED` и провести ручной release через операционный процесс.

## Git hygiene

- Не коммитить runtime/generated файлы:
  - `bot.db`
  - `graphify-out/`
  - `__pycache__/`
  - `.pytest_cache/`
  - `.venv/`
  - `testsprite_tests/`
  - ad-hoc скрипты `dump.py`, `migrate.py` (если они не продуктовые)
