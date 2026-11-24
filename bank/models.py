from dataclasses import dataclass
from decimal import Decimal


def cents_to_decimal(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class Account:
    id: int
    owner: str
    balance_cents: int
    created_at: str

    @property
    def balance(self) -> Decimal:
        return cents_to_decimal(self.balance_cents)


@dataclass(frozen=True)
class Transaction:
    id: int
    account_id: int
    type: str  # DEPOSIT, WITHDRAWAL, TRANSFER_IN, TRANSFER_OUT
    amount_cents: int
    balance_after_cents: int
    description: str
    created_at: str

    @property
    def amount(self) -> Decimal:
        return cents_to_decimal(self.amount_cents)

    @property
    def balance_after(self) -> Decimal:
        return cents_to_decimal(self.balance_after_cents)
