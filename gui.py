import tkinter as tk
from datetime import date, datetime, timedelta, timezone

from bank import BankError, BankService
from bank.models import cents_to_decimal
from bank.services import to_cents

CURRENCY = "R"  # South African Rand

# ---- palette ----
TEAL = "#00747E"
TEAL_DARK = "#005A63"
ORANGE = "#F28C28"
ORANGE_DARK = "#D9761A"
BG = "#F1F4F5"
CARD = "#FFFFFF"
TEXT = "#1E2A32"
MUTED = "#6B7780"
GREEN = "#1B8A3D"
RED = "#C62828"
LINE = "#DDE3E6"
SOFT = "#DCE6E8"
FONT = "Segoe UI"

TYPE_NAMES = {
    "DEPOSIT": "Deposit",
    "WITHDRAWAL": "Cash withdrawal",
    "TRANSFER_IN": "Payment received",
    "TRANSFER_OUT": "Payment sent",
}


# ---------- helpers ----------
def money(value) -> str:
    return f"{CURRENCY}{value:,.2f}"


def local_dt(text: str):
    """Database times are UTC; show them in the device's local time."""
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc).astimezone()
    except ValueError:
        return None


def fmt_dt(text: str) -> str:
    dt = local_dt(text)
    return dt.strftime("%d %b %Y, %H:%M") if dt else text


def day_label(text: str) -> str:
    dt = local_dt(text)
    if dt is None:
        return text
    if dt.date() == date.today():
        return "Today"
    if dt.date() == date.today() - timedelta(days=1):
        return "Yesterday"
    return dt.strftime("%d %B %Y")


def clean_amount(raw: str) -> str:
    """Accept '1 250,50' as well as '1250.50'."""
    return raw.strip().replace(" ", "").replace(",", ".")


# ---------- reusable widgets ----------
class Btn(tk.Label):
    """Flat clickable button that looks the same on every platform."""

    def __init__(self, parent, text, command, bg=ORANGE, fg="white",
                 hover=ORANGE_DARK, size=12, pady=12):
        super().__init__(parent, text=text, bg=bg, fg=fg, cursor="hand2",
                         font=(FONT, size, "bold"), pady=pady)
        self._normal, self._over, self._click = bg, hover, command
        self.bind("<Enter>", lambda e: self._paint(self._over))
        self.bind("<Leave>", lambda e: self._paint(self._normal))
        self.bind("<Button-1>", lambda e: self._click())

    def _paint(self, colour):
        try:
            self.config(bg=colour)
        except tk.TclError:
            pass


class Field(tk.Frame):
    """Label + text box with an optional prefix such as the Rand sign."""

    def __init__(self, parent, label, show="", prefix=None, bg=CARD, label_fg=MUTED):
        super().__init__(parent, bg=bg)
        tk.Label(self, text=label, bg=bg, fg=label_fg, font=(FONT, 9)).pack(anchor="w")
        self.box = tk.Frame(self, bg="white", highlightthickness=1, highlightbackground=LINE)
        self.box.pack(fill="x", pady=(3, 10))
        if prefix:
            tk.Label(self.box, text=prefix, bg="white", fg=MUTED,
                     font=(FONT, 12, "bold")).pack(side="left", padx=(10, 0))
        self.entry = tk.Entry(self.box, show=show, relief="flat", bg="white", fg=TEXT,
                              insertbackground=TEXT, font=(FONT, 12))
        self.entry.pack(fill="x", padx=8, pady=9)
        self.entry.bind("<FocusIn>", lambda e: self.box.config(highlightbackground=TEAL))
        self.entry.bind("<FocusOut>", lambda e: self.box.config(highlightbackground=LINE))

    def get(self) -> str:
        return self.entry.get()

    def set(self, value: str) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, value)


class ScrollFrame(tk.Frame):


    def __init__(self, parent, bg=BG):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self._win, width=e.width))
        self.canvas.pack(fill="both", expand=True)
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(seq, self._wheel)

    def _wheel(self, event):
        try:
            if self.inner.winfo_height() <= self.canvas.winfo_height():
                return
            up = event.num == 4 or getattr(event, "delta", 0) > 0
            self.canvas.yview_scroll(-2 if up else 2, "units")
        except tk.TclError:
            pass

    def destroy(self):
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.unbind_all(seq)
        super().destroy()


def card_frame(parent):
    return tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=LINE)


def section_title(parent, text, link_text=None, link_cmd=None):
    row = tk.Frame(parent, bg=BG)
    tk.Label(row, text=text, bg=BG, fg=TEXT, font=(FONT, 11, "bold")).pack(side="left")
    if link_text:
        link = tk.Label(row, text=link_text, bg=BG, fg=TEAL, cursor="hand2",
                        font=(FONT, 9, "bold"))
        link.pack(side="right")
        link.bind("<Button-1>", lambda e: link_cmd())
    return row


def kv_card(parent, rows):
    """White card of label/value rows (used on review and result screens)."""
    card = card_frame(parent)
    for i, (key, value) in enumerate(rows):
        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x", padx=14, pady=8)
        tk.Label(row, text=key, bg=CARD, fg=MUTED, font=(FONT, 9)).pack(side="left")
        tk.Label(row, text=value, bg=CARD, fg=TEXT, font=(FONT, 10, "bold"),
                 justify="right", wraplength=230).pack(side="right")
        if i < len(rows) - 1:
            tk.Frame(card, bg=LINE, height=1).pack(fill="x", padx=14)
    return card


def tx_row(parent, t, with_balance=False):
    incoming = t.type in ("DEPOSIT", "TRANSFER_IN")
    row = tk.Frame(parent, bg=CARD)
    inner = tk.Frame(row, bg=CARD)
    inner.pack(fill="x", padx=14, pady=10)
    left = tk.Frame(inner, bg=CARD)
    left.pack(side="left")
    tk.Label(left, text=t.description or TYPE_NAMES.get(t.type, t.type), bg=CARD,
             fg=TEXT, font=(FONT, 10, "bold")).pack(anchor="w")
    tk.Label(left, text=fmt_dt(t.created_at), bg=CARD, fg=MUTED,
             font=(FONT, 8)).pack(anchor="w")
    right = tk.Frame(inner, bg=CARD)
    right.pack(side="right")
    sign = "+" if incoming else "-"
    tk.Label(right, text=f"{sign}{money(t.amount)}", bg=CARD,
             fg=GREEN if incoming else RED, font=(FONT, 10, "bold")).pack(anchor="e")
    if with_balance:
        tk.Label(right, text=f"Balance {money(t.balance_after)}", bg=CARD, fg=MUTED,
                 font=(FONT, 8)).pack(anchor="e")
    tk.Frame(row, bg=LINE, height=1).pack(fill="x")
    return row


class ResultView(tk.Frame):
   

    def __init__(self, parent, title, subtitle="", big="", rows=(), button_text="Done",
                 command=None, bg=BG, fg=TEXT, sub=MUTED):
        super().__init__(parent, bg=bg)
        wrap = tk.Frame(self, bg=bg)
        wrap.pack(fill="x", padx=24, pady=(36, 0))
        mark = tk.Canvas(wrap, width=84, height=84, bg=bg, highlightthickness=0)
        mark.pack(pady=(0, 14))
        mark.create_oval(4, 4, 80, 80, fill=GREEN, outline="")
        mark.create_text(42, 42, text="✓", fill="white", font=(FONT, 34, "bold"))
        tk.Label(wrap, text=title, bg=bg, fg=fg, font=(FONT, 16, "bold")).pack()
        if subtitle:
            tk.Label(wrap, text=subtitle, bg=bg, fg=sub, font=(FONT, 10),
                     wraplength=320, justify="center").pack(pady=(4, 0))
        if big:
            tk.Label(wrap, text=big, bg=bg, fg=ORANGE, font=(FONT, 28, "bold")).pack(pady=(14, 0))
        if rows:
            kv_card(wrap, rows).pack(fill="x", pady=(20, 0))
        Btn(wrap, button_text, command).pack(fill="x", pady=(24, 0))


# ---------- application ----------
class BankApp(tk.Tk):
    IDLE_MS = 180_000  # auto logout after 3 minutes of no activity

    def __init__(self, db_path: str = "bank.db"):
        super().__init__()
        self.title("HONEST Bank")
        height = min(740, self.winfo_screenheight() - 120)
        x = (self.winfo_screenwidth() - 400) // 2
        y = max((self.winfo_screenheight() - height) // 2 - 20, 0)
        self.geometry(f"400x{height}+{x}+{y}")
        self.minsize(360, 560)
        self.configure(bg=BG)

        self.bank = BankService(db_path)
        self.show_balance = True
        self.logged_in = False
        self._idle_job = None

        self.container = tk.Frame(self, bg=BG)
        self.container.pack(fill="both", expand=True)
        self.bind_all("<Any-KeyPress>", self._reset_idle)
        self.bind_all("<Any-ButtonPress>", self._reset_idle)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.show_login()

    # navigation
    def _clear(self):
        for child in self.container.winfo_children():
            child.destroy()

    def show_login(self, notice=None, prefill=None):
        self.logged_in = False
        self._reset_idle()
        self.show_balance = True
        self._clear()
        LoginScreen(self.container, self, notice, prefill).pack(fill="both", expand=True)

    def show_register(self):
        self._clear()
        RegisterScreen(self.container, self).pack(fill="both", expand=True)

    def show_welcome(self, acct):
        self._clear()
        ResultView(
            self.container, "Account opened", f"Welcome to HONEST Bank, {acct.owner}!",
            big=str(acct.id),
            rows=[("Account type", "Easy Account"), ("Opening balance", money(acct.balance))],
            button_text="Continue to log in", bg=TEAL, fg="white", sub="#CFE8EB",
            command=lambda: self.show_login(prefill=acct.id),
        ).pack(fill="both", expand=True)
        tk.Label(self.container, text="This is your account number - keep it safe.",
                 bg=TEAL, fg="#CFE8EB", font=(FONT, 9)).pack(side="bottom", pady=14)

    def show_shell(self, account_id: int):
        self.logged_in = True
        self._reset_idle()
        self._clear()
        Shell(self.container, self, account_id).pack(fill="both", expand=True)

    # inactivity logout
    def _reset_idle(self, event=None):
        if self._idle_job is not None:
            self.after_cancel(self._idle_job)
            self._idle_job = None
        if self.logged_in:
            self._idle_job = self.after(self.IDLE_MS, self._idle_logout)

    def _idle_logout(self):
        self._idle_job = None
        if self.logged_in:
            self.show_login(notice="You were logged out because of inactivity.")

    def _on_close(self):
        self.bank.close()
        self.destroy()


# ---------- login / register ----------
class LoginScreen(tk.Frame):
    def __init__(self, parent, app: BankApp, notice=None, prefill=None):
        super().__init__(parent, bg=TEAL)
        self.app = app
        tk.Label(self, text="HONEST Bank - not a real bank", bg=TEAL, fg="#8CC4CA",
                 font=(FONT, 8)).pack(side="bottom", pady=12)

        inner = tk.Frame(self, bg=TEAL)
        inner.pack(expand=True, fill="x", padx=30)

        logo = tk.Canvas(inner, width=90, height=90, bg=TEAL, highlightthickness=0)
        logo.pack()
        logo.create_oval(3, 3, 87, 87, fill="white", outline="")
        logo.create_text(45, 45, text="HB", fill=TEAL, font=(FONT, 28, "bold"))
        tk.Label(inner, text="HONEST Bank", bg=TEAL, fg="white",
                 font=(FONT, 22, "bold")).pack(pady=(10, 0))
        tk.Label(inner, text="Banking made simple", bg=TEAL, fg="#CFE8EB",
                 font=(FONT, 10)).pack(pady=(0, 24))

        self.acc = Field(inner, "Account number", bg=TEAL, label_fg="#CFE8EB")
        self.acc.pack(fill="x")
        self.pin = Field(inner, "PIN", show="•", bg=TEAL, label_fg="#CFE8EB")
        self.pin.pack(fill="x")
        if prefill:
            self.acc.set(str(prefill))

        self.msg = tk.Label(inner, text=notice or "", bg=TEAL, fg="#FFE0B2",
                            font=(FONT, 9), wraplength=320)
        self.msg.pack(pady=(0, 8))
        Btn(inner, "Log in", self.submit).pack(fill="x")

        link = tk.Label(inner, text="New here? Open an account", bg=TEAL, fg="white",
                        cursor="hand2", font=(FONT, 10, "underline"))
        link.pack(pady=18)
        link.bind("<Button-1>", lambda e: app.show_register())

        self.acc.entry.bind("<Return>", lambda e: self.pin.entry.focus())
        self.pin.entry.bind("<Return>", lambda e: self.submit())
        (self.pin if prefill else self.acc).entry.focus()

    def submit(self):
        try:
            account_id = int(self.acc.get().strip())
        except ValueError:
            self.msg.config(text="Account number must be a number.")
            return
        try:
            self.app.bank.authenticate(account_id, self.pin.get())
        except BankError as e:
            self.msg.config(text=str(e))
            self.pin.set("")
            return
        self.app.show_shell(account_id)


class RegisterScreen(tk.Frame):
    def __init__(self, parent, app: BankApp):
        super().__init__(parent, bg=BG)
        self.app = app

        header = tk.Frame(self, bg=TEAL)
        header.pack(fill="x")
        back = tk.Label(header, text="‹  Back", bg=TEAL, fg="white", cursor="hand2",
                        font=(FONT, 11, "bold"), padx=16, pady=14)
        back.pack(side="left")
        back.bind("<Button-1>", lambda e: app.show_login())
        tk.Label(header, text="Open an account", bg=TEAL, fg="white",
                 font=(FONT, 13, "bold")).pack(side="left", padx=4)

        tk.Label(self, text="Easy Account - no monthly fee in this demo.", bg=BG, fg=MUTED,
                 font=(FONT, 9)).pack(anchor="w", padx=18, pady=(16, 6))
        card = card_frame(self)
        card.pack(fill="x", padx=16)
        pad = tk.Frame(card, bg=CARD)
        pad.pack(fill="x", padx=14, pady=(14, 4))
        self.name = Field(pad, "Full name")
        self.name.pack(fill="x")
        self.pin = Field(pad, "Choose a 4-digit PIN", show="•")
        self.pin.pack(fill="x")
        self.pin2 = Field(pad, "Confirm PIN", show="•")
        self.pin2.pack(fill="x")
        self.deposit = Field(pad, "Opening deposit (optional)", prefix=CURRENCY)
        self.deposit.pack(fill="x")
        self.deposit.set("0")

        self.msg = tk.Label(self, text="", bg=BG, fg=RED, font=(FONT, 9),
                            wraplength=340, justify="left")
        self.msg.pack(anchor="w", padx=18, pady=(8, 0))
        Btn(self, "Open account", self.submit).pack(fill="x", padx=16, pady=12)
        self.name.entry.focus()

    def submit(self):
        if self.pin.get() != self.pin2.get():
            self.msg.config(text="The PINs do not match.")
            return
        try:
            acct = self.app.bank.create_account(
                self.name.get(), self.pin.get(), clean_amount(self.deposit.get()) or "0")
        except BankError as e:
            self.msg.config(text=str(e))
            return
        self.app.show_welcome(acct)


# ---------- main shell with bottom navigation ----------
class Shell(tk.Frame):
    TABS = [("accounts", "⌂", "Accounts"), ("transact", "⇄", "Transact"),
            ("history", "≡", "History"), ("profile", "☺", "Profile")]

    def __init__(self, parent, app: BankApp, account_id: int):
        super().__init__(parent, bg=BG)
        self.app = app
        self.bank = app.bank
        self.account_id = account_id
        self.screen = None
        owner = self.bank.get_account(account_id).owner
        self.first_name = owner.split()[0]

        header = tk.Frame(self, bg=TEAL)
        header.pack(side="top", fill="x")
        self.title = tk.Label(header, text="", bg=TEAL, fg="white",
                              font=(FONT, 15, "bold"), padx=16, pady=14)
        self.title.pack(side="left")
        out = tk.Label(header, text="Log out", bg=TEAL, fg="white", cursor="hand2",
                       font=(FONT, 10, "bold"), padx=16)
        out.pack(side="right")
        out.bind("<Button-1>", lambda e: app.show_login())

        nav = tk.Frame(self, bg=CARD)
        nav.pack(side="bottom", fill="x")
        tk.Frame(self, bg=LINE, height=1).pack(side="bottom", fill="x")
        self.nav_items = {}
        for key, glyph, label in self.TABS:
            item = tk.Frame(nav, bg=CARD, cursor="hand2")
            item.pack(side="left", expand=True, fill="x")
            g = tk.Label(item, text=glyph, bg=CARD, fg=MUTED, font=(FONT, 16), cursor="hand2")
            t = tk.Label(item, text=label, bg=CARD, fg=MUTED, font=(FONT, 8), cursor="hand2")
            g.pack(pady=(8, 0))
            t.pack(pady=(0, 8))
            for w in (item, g, t):
                w.bind("<Button-1>", lambda e, k=key: self.goto(k))
            self.nav_items[key] = (g, t)

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(fill="both", expand=True)
        self.goto("accounts")

    def goto(self, key, **kwargs):
        if self.screen is not None:
            self.screen.destroy()
        screens = {"accounts": AccountsScreen, "transact": TransactScreen,
                   "history": HistoryScreen, "profile": ProfileScreen}
        self.screen = screens[key](self.content, self, **kwargs)
        self.screen.pack(fill="both", expand=True)
        for k, (g, t) in self.nav_items.items():
            colour = TEAL if k == key else MUTED
            g.config(fg=colour)
            t.config(fg=colour)
        titles = {"accounts": f"Hi, {self.first_name}", "transact": "Transact",
                  "history": "Transaction history", "profile": "Profile"}
        self.title.config(text=titles[key])


class AccountsScreen(tk.Frame):
    def __init__(self, parent, shell: Shell):
        super().__init__(parent, bg=BG)
        self.shell = shell
        self.acct = shell.bank.get_account(shell.account_id)

        card = card_frame(self)
        card.pack(fill="x", padx=16, pady=(16, 10))
        tk.Frame(card, bg=ORANGE, width=5).pack(side="left", fill="y")
        inner = tk.Frame(card, bg=CARD)
        inner.pack(side="left", fill="both", expand=True, padx=14, pady=12)
        tk.Label(inner, text="Easy Account", bg=CARD, fg=TEXT,
                 font=(FONT, 11, "bold")).pack(anchor="w")
        tk.Label(inner, text=f"Account no. {self.acct.id}", bg=CARD, fg=MUTED,
                 font=(FONT, 9)).pack(anchor="w")
        tk.Label(inner, text="Available balance", bg=CARD, fg=MUTED,
                 font=(FONT, 9)).pack(anchor="w", pady=(12, 0))
        self.balance_lbl = tk.Label(inner, text="", bg=CARD, fg=TEAL, font=(FONT, 24, "bold"))
        self.balance_lbl.pack(anchor="w")
        self.toggle_lbl = tk.Label(inner, text="", bg=CARD, fg=TEAL, cursor="hand2",
                                   font=(FONT, 9, "underline"))
        self.toggle_lbl.pack(anchor="w", pady=(2, 0))
        self.toggle_lbl.bind("<Button-1>", lambda e: self.toggle())
        self.render_balance()

        section_title(self, "Quick actions").pack(fill="x", padx=16, pady=(10, 6))
        row = tk.Frame(self, bg=BG)
        row.pack(fill="x", padx=12)
        actions = [
            ("+", "Deposit", lambda: shell.goto("transact", mode="deposit")),
            ("-", "Withdraw", lambda: shell.goto("transact", mode="withdraw")),
            ("→", "Pay", lambda: shell.goto("transact", mode="transfer")),
            ("≡", "History", lambda: shell.goto("history")),
        ]
        for i, (glyph, text, cmd) in enumerate(actions):
            row.columnconfigure(i, weight=1, uniform="tiles")
            self._tile(row, glyph, text, cmd).grid(row=0, column=i, sticky="nsew", padx=4)

        section_title(self, "Recent transactions", "See all",
                      lambda: shell.goto("history")).pack(fill="x", padx=16, pady=(18, 6))
        txs = shell.bank.statement(shell.account_id, limit=5)
        box = card_frame(self)
        box.pack(fill="x", padx=16)
        if not txs:
            tk.Label(box, text="No transactions yet.\nMake a deposit to get started.",
                     bg=CARD, fg=MUTED, font=(FONT, 10), pady=24).pack()
        for t in txs:
            tx_row(box, t).pack(fill="x")

    @staticmethod
    def _tile(parent, glyph, text, command):
        f = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=LINE,
                     cursor="hand2")
        g = tk.Label(f, text=glyph, bg=CARD, fg=ORANGE, font=(FONT, 18, "bold"), cursor="hand2")
        t = tk.Label(f, text=text, bg=CARD, fg=TEXT, font=(FONT, 9), cursor="hand2")
        g.pack(pady=(10, 0))
        t.pack(pady=(0, 10))
        for w in (f, g, t):
            w.bind("<Button-1>", lambda e: command())
        return f

    def toggle(self):
        self.shell.app.show_balance = not self.shell.app.show_balance
        self.render_balance()

    def render_balance(self):
        show = self.shell.app.show_balance
        self.balance_lbl.config(text=money(self.acct.balance) if show else f"{CURRENCY} ••••••")
        self.toggle_lbl.config(text="Hide balance" if show else "Show balance")


class TransactScreen(tk.Frame):
    MODES = {"deposit": "Deposit", "withdraw": "Withdraw", "transfer": "Pay"}
    BLURBS = {
        "deposit": "Add money to your Easy Account.",
        "withdraw": "Withdraw cash from your Easy Account.",
        "transfer": "Pay another Python Bank account instantly.",
    }

    def __init__(self, parent, shell: Shell, mode="deposit"):
        super().__init__(parent, bg=BG)
        self.shell = shell
        self.bank = shell.bank
        self.mode = mode
        self.pending = None
        self._busy = False

        self.seg = tk.Frame(self, bg=BG)
        self.labels = {}
        for key, text in self.MODES.items():
            lbl = tk.Label(self.seg, text=text, font=(FONT, 10, "bold"), cursor="hand2", pady=9)
            lbl.pack(side="left", expand=True, fill="x")
            lbl.bind("<Button-1>", lambda e, k=key: self.set_mode(k))
            self.labels[key] = lbl
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill="both", expand=True)
        self.set_mode(mode)

    def _clear_body(self):
        for child in self.body.winfo_children():
            child.destroy()

    def set_mode(self, mode):
        self.mode = mode
        for key, lbl in self.labels.items():
            active = key == mode
            lbl.config(bg=TEAL if active else SOFT, fg="white" if active else TEAL)
        self.show_form()

    # step 1: form
    def show_form(self, error="", dest="", amount=""):
        self._clear_body()
        self.seg.pack(fill="x", padx=16, pady=(16, 8), before=self.body)
        acct = self.bank.get_account(self.shell.account_id)

        card = card_frame(self.body)
        card.pack(fill="x", padx=16, pady=8)
        pad = tk.Frame(card, bg=CARD)
        pad.pack(fill="x", padx=14, pady=14)
        tk.Label(pad, text=self.BLURBS[self.mode], bg=CARD, fg=MUTED, font=(FONT, 9),
                 wraplength=320, justify="left").pack(anchor="w", pady=(0, 10))
        self.dest = None
        if self.mode == "transfer":
            self.dest = Field(pad, "Recipient account number")
            self.dest.pack(fill="x")
            self.dest.set(dest)
        self.amount = Field(pad, "Amount", prefix=CURRENCY)
        self.amount.pack(fill="x")
        self.amount.set(amount)
        if self.mode != "deposit":
            tk.Label(pad, text=f"Available: {money(acct.balance)}", bg=CARD, fg=MUTED,
                     font=(FONT, 9)).pack(anchor="w")

        self.error = tk.Label(self.body, text=error, bg=BG, fg=RED, font=(FONT, 9),
                              wraplength=340, justify="left")
        self.error.pack(anchor="w", padx=18)
        Btn(self.body, "Continue", self.review).pack(fill="x", padx=16, pady=12)
        self.amount.entry.bind("<Return>", lambda e: self.review())
        (self.dest or self.amount).entry.focus()

    # step 2: review
    def review(self):
        raw_amount = self.amount.get()
        raw_dest = self.dest.get() if self.dest else ""
        recipient = None
        try:
            cents = to_cents(clean_amount(raw_amount))
            acct = self.bank.get_account(self.shell.account_id)
            if self.mode == "transfer":
                try:
                    dest_id = int(raw_dest.strip())
                except ValueError:
                    raise BankError("Enter a valid recipient account number.")
                if dest_id == acct.id:
                    raise BankError("You cannot pay your own account.")
                recipient = self.bank.get_account(dest_id)
            if self.mode != "deposit" and cents > acct.balance_cents:
                raise BankError("Insufficient funds.")
        except BankError as e:
            self.error.config(text=str(e))
            return
        self.pending = (cents, recipient, raw_dest, raw_amount)
        self.show_review(acct, cents, recipient)

    def show_review(self, acct, cents, recipient, error=""):
        self.seg.pack_forget()
        self._clear_body()
        amount = money(cents_to_decimal(cents))
        tk.Label(self.body, text="Review and confirm", bg=BG, fg=TEXT,
                 font=(FONT, 14, "bold")).pack(anchor="w", padx=18, pady=(18, 8))
        me = f"{acct.owner} ({acct.id})"
        if self.mode == "transfer":
            rows = [("Transaction", "Payment"), ("From", me),
                    ("To", f"{recipient.owner} ({recipient.id})"), ("Amount", amount)]
        else:
            rows = [("Transaction", self.MODES[self.mode]), ("Account", me), ("Amount", amount)]
        kv_card(self.body, rows).pack(fill="x", padx=16)
        self.error = tk.Label(self.body, text=error, bg=BG, fg=RED, font=(FONT, 9),
                              wraplength=340, justify="left")
        self.error.pack(anchor="w", padx=18, pady=(8, 0))
        Btn(self.body, "Confirm", self.confirm).pack(fill="x", padx=16, pady=(8, 6))
        Btn(self.body, "Back", self.back, bg=BG, fg=TEAL, hover=SOFT).pack(fill="x", padx=16)

    def back(self):
        _, _, raw_dest, raw_amount = self.pending
        self.show_form(dest=raw_dest, amount=raw_amount)

    # step 3: confirm + result
    def confirm(self):
        if self._busy:
            return
        self._busy = True
        cents, recipient, _, _ = self.pending
        amount = cents_to_decimal(cents)
        acct_id = self.shell.account_id
        try:
            if self.mode == "deposit":
                acct = self.bank.deposit(acct_id, amount)
            elif self.mode == "withdraw":
                acct = self.bank.withdraw(acct_id, amount)
            else:
                acct = self.bank.transfer(acct_id, recipient.id, amount)
        except BankError as e:
            self._busy = False
            self.error.config(text=str(e))
            return
        reference = self.bank.statement(acct_id, limit=1)[0].id
        titles = {"deposit": "Deposit successful", "withdraw": "Withdrawal successful",
                  "transfer": "Payment successful"}
        rows = [("Amount", money(amount)), ("New balance", money(acct.balance)),
                ("Reference", f"#{reference:06d}"),
                ("Date", datetime.now().strftime("%d %b %Y, %H:%M"))]
        if recipient:
            rows.insert(1, ("Paid to", f"{recipient.owner} ({recipient.id})"))
        self._clear_body()
        ResultView(self.body, titles[self.mode], rows=rows, button_text="Done",
                   command=lambda: self.shell.goto("accounts")).pack(fill="both", expand=True)


class HistoryScreen(tk.Frame):
    def __init__(self, parent, shell: Shell):
        super().__init__(parent, bg=BG)
        txs = shell.bank.statement(shell.account_id, limit=200)
        if not txs:
            tk.Label(self, text="No transactions yet.", bg=BG, fg=MUTED,
                     font=(FONT, 11)).pack(pady=50)
            return
        scroll = ScrollFrame(self)
        scroll.pack(fill="both", expand=True)
        last, card = None, None
        for t in txs:
            label = day_label(t.created_at)
            if label != last:
                tk.Label(scroll.inner, text=label, bg=BG, fg=MUTED, anchor="w",
                         font=(FONT, 9, "bold")).pack(fill="x", padx=16, pady=(14, 4))
                card = card_frame(scroll.inner)
                card.pack(fill="x", padx=16)
                last = label
            tx_row(card, t, with_balance=True).pack(fill="x")
        tk.Frame(scroll.inner, bg=BG, height=16).pack()


class ProfileScreen(tk.Frame):
    def __init__(self, parent, shell: Shell):
        super().__init__(parent, bg=BG)
        acct = shell.bank.get_account(shell.account_id)
        initials = "".join(w[0] for w in acct.owner.split()[:2]).upper() or "?"

        avatar = tk.Canvas(self, width=90, height=90, bg=BG, highlightthickness=0)
        avatar.pack(pady=(24, 8))
        avatar.create_oval(3, 3, 87, 87, fill=TEAL, outline="")
        avatar.create_text(45, 45, text=initials, fill="white", font=(FONT, 26, "bold"))
        tk.Label(self, text=acct.owner, bg=BG, fg=TEXT, font=(FONT, 15, "bold")).pack()
        tk.Label(self, text="Account holder", bg=BG, fg=MUTED, font=(FONT, 9)).pack(pady=(0, 16))

        since = local_dt(acct.created_at)
        kv_card(self, [
            ("Account number", str(acct.id)),
            ("Account type", "Easy Account"),
            ("Customer since", since.strftime("%d %B %Y") if since else acct.created_at),
        ]).pack(fill="x", padx=16)

        tk.Label(self, text="For your safety you are logged out automatically after "
                            "3 minutes of inactivity. Never share your PIN with anyone.",
                 bg=BG, fg=MUTED, font=(FONT, 9), wraplength=340, justify="left"
                 ).pack(anchor="w", padx=18, pady=16)
        Btn(self, "Log out", shell.app.show_login, bg=TEAL, hover=TEAL_DARK
            ).pack(fill="x", padx=16)


def main():
    BankApp().mainloop()


if __name__ == "__main__":
    main()
