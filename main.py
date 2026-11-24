"""Console banking app. Run with:  python main.py"""
from getpass import getpass

from bank import BankError, BankService

LINE = "-" * 50
CURRENCY = "R"  # South African Rand


def ask_int(prompt: str) -> int:
    while True:
        try:
            return int(input(prompt).strip())
        except ValueError:
            print("Please enter a number.")


def create_account(bank: BankService) -> None:
    owner = input("Full name: ")
    pin = getpass("Choose a 4-digit PIN: ")
    deposit = input(f"Initial deposit in {CURRENCY} (0 for none): ") or "0"
    acct = bank.create_account(owner, pin, deposit)
    print(f"\nAccount created! Your account number is {acct.id}. Keep it safe.")


def account_menu(bank: BankService, account_id: int) -> None:
    while True:
        acct = bank.get_account(account_id)
        print(f"\n{LINE}\n{acct.owner}  |  Account {acct.id}  |  Balance: {CURRENCY}{acct.balance:,.2f}\n{LINE}")
        print("1) Deposit\n2) Withdraw\n3) Transfer\n4) Statement\n5) Logout")
        choice = input("> ").strip()
        try:
            if choice == "1":
                bank.deposit(account_id, input(f"Amount ({CURRENCY}): "))
                print("Deposit successful.")
            elif choice == "2":
                bank.withdraw(account_id, input(f"Amount ({CURRENCY}): "))
                print("Withdrawal successful.")
            elif choice == "3":
                to_id = ask_int("Destination account number: ")
                bank.transfer(account_id, to_id, input(f"Amount ({CURRENCY}): "))
                print("Transfer successful.")
            elif choice == "4":
                print(f"\n{'Date':<20}{'Type':<14}{'Amount':>10}{'Balance':>12}")
                for t in bank.statement(account_id):
                    print(f"{t.created_at:<20}{t.type:<14}{CURRENCY + format(t.amount, ',.2f'):>10}{CURRENCY + format(t.balance_after, ',.2f'):>12}")
            elif choice == "5":
                return
            else:
                print("Invalid option.")
        except BankError as e:
            print(f"Error: {e}")


def login(bank: BankService) -> None:
    account_id = ask_int("Account number: ")
    pin = getpass("PIN: ")
    bank.authenticate(account_id, pin)
    account_menu(bank, account_id)


def main() -> None:
    bank = BankService("bank.db")
    try:
        while True:
            print(f"\n{LINE}\n  PYTHON BANK\n{LINE}\n1) Create account\n2) Login\n3) Exit")
            choice = input("> ").strip()
            try:
                if choice == "1":
                    create_account(bank)
                elif choice == "2":
                    login(bank)
                elif choice == "3":
                    print("Goodbye!")
                    break
                else:
                    print("Invalid option.")
            except BankError as e:
                print(f"Error: {e}")
    finally:
        bank.close()


if __name__ == "__main__":
    main()
