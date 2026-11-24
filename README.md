# HONEST Bank System

A mobile-style banking app built with Tkinter (a console version is included too).
Everything uses the Python standard library (3.9+). All amounts are in **South African Rand (R)**.

The layout is inspired by modern South African banking apps (teal header, account card,
quick actions, review-and-confirm payments, bottom navigation). It is a demo and is not
affiliated with any bank.

## App screens

- **Login / Open an account** - account number + PIN, with a registration flow
- **Accounts** - account card with balance (hide/show), quick actions, recent transactions
- **Transact** - Deposit, Withdraw, Pay another account; review screen, then confirmation with a reference number
- **History** - full transaction list grouped by day (Today, Yesterday, ...), with running balance
- **Profile** - account details and log out
- Automatic logout after 3 minutes of inactivity

## Security / reliability

- PINs stored as salted PBKDF2 hashes
- Money stored as integer cents (no floating-point errors)
- Payments are atomic (both accounts update, or neither)
- Amounts accept `1250.50` or `1 250,50`

## Structure

```
BankSystem/
├── gui.py             # mobile-style app (entry point)
├── main.py            # console version
├── bank/              # business logic, database, models, errors
├── tests/test_bank.py # unit tests
└── .vscode/           # launch, settings, extension recommendations
```

## Open in Visual Studio Code

1. Install Python from python.org (tick "Add python.exe to PATH") and VS Code.
2. File > Open Folder... and choose `BankSystem`.
3. Accept the prompt to install the recommended **Python** extension.
4. `Ctrl+Shift+P` > "Python: Select Interpreter" and pick Python 3.9+.
5. `Ctrl+Shift+D`, choose **Bank GUI (gui.py)** and press F5.

## Run from a terminal

```
python gui.py
python main.py
python -m unittest discover -s tests -v
```

## Customising

Colours and the currency symbol are constants at the top of `gui.py`
(`TEAL`, `ORANGE`, `CURRENCY`, ...).
