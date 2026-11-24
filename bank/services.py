import hashlib
import hmac
import os
from decimal import Decimal, InvalidOperation

from . import database
from .exceptions import (
    AccountNotFoundError,
    AuthenticationError,
    BankError,
    InsufficientFundsError,
    InvalidAmountError,
)
from .models import Account, Transaction

_ITERATIONS = 100_000


def _hash_pin(pin: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, _ITERATIONS).hex()


def to_cents(amount) -> int:
    """Convert a user amount to integer cents. Rejects <= 0 or > 2 decimals."""
    try:
        value = Decimal(str(amount))
    except InvalidOperation:
        raise InvalidAmountError("Amount must be a number.")
    if not value.is_finite() or value <= 0:
        raise InvalidAmountError("Amount must be greater than zero.")
    if value != value.quantize(Decimal("0.01")):
        raise InvalidAmountError("Amount can have at most 2 decimal places.")
    return int(value * 100)


class BankService:
    def __init__(self, db_path: str = "bank.db"):
        self.conn = database.connect(db_path)

    def close(self) -> None:
        self.conn.close()

    # ---------- accounts ----------
    def create_account(self, owner: str, pin: str, initial_deposit=0) -> Account:
        owner = owner.strip()
        if not owner:
            raise BankError("Owner name is required.")
        if not (pin.isdigit() and len(pin) == 4):
            raise BankError("PIN must be exactly 4 digits.")
        try:
            initial = Decimal(str(initial_deposit))
        except InvalidOperation:
            raise InvalidAmountError("Initial deposit must be a number.")
        cents = to_cents(initial) if initial != 0 else 0

        salt = os.urandom(16)
        with self.conn:
            account_id = self.conn.execute(
                "SELECT COALESCE(MAX(id), 1000) + 1 FROM accounts"
            ).fetchone()[0]
            self.conn.execute(
                "INSERT INTO accounts (id, owner, pin_hash, salt, balance_cents) "
                "VALUES (?, ?, ?, ?, 0)",
                (account_id, owner, _hash_pin(pin, salt), salt.hex()),
            )
            if cents:
                self._apply(account_id, cents, "DEPOSIT", "Initial deposit")
        return self.get_account(account_id)

    def get_account(self, account_id: int) -> Account:
        row = self.conn.execute(
            "SELECT id, owner, balance_cents, created_at FROM accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        if row is None:
            raise AccountNotFoundError(f"Account {account_id} not found.")
        return Account(**dict(row))

    def authenticate(self, account_id: int, pin: str) -> Account:
        row = self.conn.execute(
            "SELECT pin_hash, salt FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        # Same error for unknown account and wrong PIN
        if row is None or not hmac.compare_digest(
            row["pin_hash"], _hash_pin(pin, bytes.fromhex(row["salt"]))
        ):
            raise AuthenticationError("Invalid account number or PIN.")
        return self.get_account(account_id)

    # ---------- money movement ----------
    def deposit(self, account_id: int, amount, description: str = "Deposit") -> Account:
        cents = to_cents(amount)
        with self.conn:
            self._apply(account_id, cents, "DEPOSIT", description)
        return self.get_account(account_id)

    def withdraw(self, account_id: int, amount, description: str = "Withdrawal") -> Account:
        cents = to_cents(amount)
        with self.conn:
            self._apply(account_id, -cents, "WITHDRAWAL", description)
        return self.get_account(account_id)

    def transfer(self, from_id: int, to_id: int, amount) -> Account:
        if from_id == to_id:
            raise BankError("Cannot transfer to the same account.")
        cents = to_cents(amount)
        self.get_account(to_id)  # raises if destination doesn't exist
        with self.conn:  # atomic: both sides succeed or neither does
            self._apply(from_id, -cents, "TRANSFER_OUT", f"Transfer to {to_id}")
            self._apply(to_id, cents, "TRANSFER_IN", f"Transfer from {from_id}")
        return self.get_account(from_id)

    def _apply(self, account_id: int, delta_cents: int, tx_type: str, description: str) -> None:
        row = self.conn.execute(
            "SELECT balance_cents FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        if row is None:
            raise AccountNotFoundError(f"Account {account_id} not found.")
        new_balance = row["balance_cents"] + delta_cents
        if new_balance < 0:
            raise InsufficientFundsError("Insufficient funds.")
        self.conn.execute(
            "UPDATE accounts SET balance_cents = ? WHERE id = ?",
            (new_balance, account_id),
        )
        self.conn.execute(
            "INSERT INTO transactions "
            "(account_id, type, amount_cents, balance_after_cents, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (account_id, tx_type, abs(delta_cents), new_balance, description),
        )

    # ---------- history ----------
    def statement(self, account_id: int, limit: int = 20) -> list[Transaction]:
        rows = self.conn.execute(
            "SELECT * FROM transactions WHERE account_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (account_id, limit),
        ).fetchall()
        return [Transaction(**dict(r)) for r in rows]
