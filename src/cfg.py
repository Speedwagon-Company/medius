from __future__ import annotations

import os

EMBED_PRIMARY_COLOR = int(os.getenv("EMBED_PRIMARY_COLOR", "0x2f3136"), 16)
EMBED_SUC_COLOR = int(os.getenv("EMBED_SUC_COLOR", "0x57F287"), 16)
EMBED_ERR_COLOR = int(os.getenv("EMBED_ERR_COLOR", "0xED4245"), 16)

SEND_WALLET_TRIES = int(os.getenv("SEND_WALLET_TRIES", "3"))
TRANSACTIONS_LOG_CHAN_ID = int(os.getenv("TRANSACTIONS_LOG_CHAN_ID", "0"))
GENERAL_LOG_CHAN_ID = int(os.getenv("GENERAL_LOG_CHAN_ID", "0"))
