from enum import Enum


class TradeRoles(Enum):
    BUYER = "buyer"
    SELLER = "seller"

    # Legacy aliases kept for existing code compatibility.
    SENDER = "buyer"
    RECIEVER = "seller"
