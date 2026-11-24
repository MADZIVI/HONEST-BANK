import unittest
from decimal import Decimal

from bank import (
    AccountNotFoundError,
    AuthenticationError,
    BankError,
    BankService,
    InsufficientFundsError,
    InvalidAmountError,
)


class BankTests(unittest.TestCase):
    def setUp(self):
        self.bank = BankService(":memory:")
        self.a = self.bank.create_account("Alice", "1234", "100.00")
        self.b = self.bank.create_account("Bob", "4321")

    def tearDown(self):
        self.bank.close()

    def test_initial_deposit(self):
        self.assertEqual(self.a.balance, Decimal("100.00"))
        self.assertEqual(self.b.balance, Decimal("0.00"))

    def test_deposit_and_withdraw(self):
        self.bank.deposit(self.a.id, "50.25")
        acct = self.bank.withdraw(self.a.id, "20")
        self.assertEqual(acct.balance, Decimal("130.25"))

    def test_overdraw_rejected(self):
        with self.assertRaises(InsufficientFundsError):
            self.bank.withdraw(self.a.id, "100.01")
        self.assertEqual(self.bank.get_account(self.a.id).balance, Decimal("100.00"))

    def test_invalid_amounts(self):
        for bad in ("0", "-5", "abc", "1.234"):
            with self.assertRaises(InvalidAmountError):
                self.bank.deposit(self.a.id, bad)

    def test_transfer(self):
        self.bank.transfer(self.a.id, self.b.id, "40")
        self.assertEqual(self.bank.get_account(self.a.id).balance, Decimal("60.00"))
        self.assertEqual(self.bank.get_account(self.b.id).balance, Decimal("40.00"))

    def test_failed_transfer_is_atomic(self):
        with self.assertRaises(InsufficientFundsError):
            self.bank.transfer(self.a.id, self.b.id, "500")
        self.assertEqual(self.bank.get_account(self.b.id).balance, Decimal("0.00"))

    def test_transfer_errors(self):
        with self.assertRaises(BankError):
            self.bank.transfer(self.a.id, self.a.id, "1")
        with self.assertRaises(AccountNotFoundError):
            self.bank.transfer(self.a.id, 9999, "1")

    def test_authentication(self):
        self.assertEqual(self.bank.authenticate(self.a.id, "1234").id, self.a.id)
        with self.assertRaises(AuthenticationError):
            self.bank.authenticate(self.a.id, "0000")
        with self.assertRaises(AuthenticationError):
            self.bank.authenticate(9999, "1234")

    def test_bad_pin_format(self):
        with self.assertRaises(BankError):
            self.bank.create_account("Eve", "12")

    def test_bad_initial_deposit(self):
        for bad in ("abc", "-5", "1.234"):
            with self.assertRaises(InvalidAmountError):
                self.bank.create_account("Eve", "1234", bad)

    def test_statement(self):
        self.bank.withdraw(self.a.id, "10")
        types = [t.type for t in self.bank.statement(self.a.id)]
        self.assertEqual(types, ["WITHDRAWAL", "DEPOSIT"])


if __name__ == "__main__":
    unittest.main()
