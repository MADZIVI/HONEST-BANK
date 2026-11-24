class BankError(Exception):
    """Base class for all banking errors."""


class AccountNotFoundError(BankError):
    pass


class AuthenticationError(BankError):
    pass


class InsufficientFundsError(BankError):
    pass


class InvalidAmountError(BankError):
    pass
