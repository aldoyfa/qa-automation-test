from pathlib import Path
import json
import re
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

BASE_URL = "https://globalsqa.com/angularJs-protractor/BankingProject/#/login"
EVIDENCE_DIR = Path("evidence")
AMOUNT_INPUT = "input[placeholder='amount']"
FORM_CONTROL = "input.form-control"

def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")

class XYZBank:
    def __init__(self, page: Page, test_name: str):
        self.page = page
        self.step = 0
        self.evidence_dir = EVIDENCE_DIR / safe_name(test_name)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def reset(self):
        last_error = None
        for _ in range(3):
            try:
                self.page.goto(BASE_URL, wait_until="domcontentloaded", timeout=45000)
                self.page.wait_for_selector("text=Customer Login", timeout=20000)
                self.page.evaluate("localStorage.clear(); sessionStorage.clear();")
                self.page.goto(BASE_URL, wait_until="domcontentloaded", timeout=45000)
                self.page.wait_for_selector("text=Customer Login", timeout=20000)
                return
            except (PlaywrightTimeoutError, PlaywrightError) as exc:
                last_error = exc
                try:
                    self.page.goto("about:blank")
                except PlaywrightError:
                    pass
        raise last_error

    def snap(self, label: str):
        self.step += 1
        self.page.screenshot(path=self.evidence_dir / f"{self.step:02d}_{safe_name(label)}.png", full_page=True)

    def storage(self, label: str):
        self.step += 1
        data = self.page.evaluate(
            """
            () => {
                const out = {};
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    out[key] = localStorage.getItem(key);
                }
                return out;
            }
            """
        )
        path = self.evidence_dir / f"{self.step:02d}_{safe_name(label)}.json"
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def text(self) -> str:
        return self.page.locator("body").inner_text()

    def click_button(self, name: str):
        self.page.get_by_role("button", name=name, exact=True).click()

    def click_button_contains(self, name: str):
        self.page.get_by_role("button", name=re.compile(re.escape(name))).click()

    def local_json(self, key: str):
        value = self.page.evaluate("key => localStorage.getItem(key)", key)
        return json.loads(value) if value else None

    def require_local_json(self, key: str):
        value = self.local_json(key)
        assert value is not None, f"{key} localStorage tidak ditemukan"
        return value

    def set_local_json(self, key: str, value):
        self.page.evaluate(
            "([key, value]) => localStorage.setItem(key, JSON.stringify(value))",
            [key, value],
        )

    def remove_local(self, key: str):
        self.page.evaluate("key => localStorage.removeItem(key)", key)

    def go_home(self):
        self.click_button("Home")
        self.page.wait_for_selector("text=Customer Login")

    def current_balance(self):
        body = self.text()
        match = re.search(r"Balance\s*:\s*(-?\d+(?:\.\d+)?)", body)
        assert match, f"Balance tidak ditemukan. Body: {body}"
        value = match.group(1)
        return float(value) if "." in value else int(value)

    def current_account_no(self):
        body = self.text()
        match = re.search(r"Account Number\s*:\s*(\d+)", body)
        assert match, f"Account Number tidak ditemukan. Body: {body}"
        return int(match.group(1))

    def login_customer(self, full_name="Hermoine Granger", expect_account=True):
        self.click_button("Customer Login")
        self.page.locator("#userSelect").select_option(label=full_name)
        self.click_button("Login")
        if expect_account:
            self.page.wait_for_selector("#accountSelect")
        else:
            self.page.wait_for_selector("text=Please open an account with us.")
        assert full_name in self.text()

    def open_manager(self):
        manager_tabs = self.page.get_by_role("button", name=re.compile("Add Customer|Open Account|Customers"))
        if manager_tabs.count() and manager_tabs.first.is_visible():
            return
        if not self.page.get_by_role("button", name="Bank Manager Login", exact=True).count():
            self.go_home()
        self.click_button("Bank Manager Login")
        self.page.wait_for_selector("text=Add Customer")

    def open_manager_tab(self, tab_name: str):
        self.open_manager()
        self.click_button(tab_name)
        if tab_name == "Add Customer":
            self.form_fields().nth(2).wait_for()
        elif tab_name == "Open Account":
            self.page.locator("#currency").wait_for()
        elif tab_name == "Customers":
            self.page.locator("table").wait_for()

    def _click_submit_with_dialog(self, selector: str) -> str:
        messages = []

        def accept_dialog(dialog):
            messages.append(dialog.message)
            dialog.accept()

        self.page.once("dialog", accept_dialog)
        locator = self.page.locator(f"xpath={selector}") if selector.lstrip().startswith("(") else self.page.locator(selector)
        locator.click()
        self.page.wait_for_timeout(500)
        assert messages, "Expected browser alert was not shown"
        return messages[0]

    def add_customer(self, first_name: str, last_name: str, post_code: str) -> str:
        self.open_manager_tab("Add Customer")
        fields = self.form_fields()
        fields.nth(0).fill(first_name)
        fields.nth(1).fill(last_name)
        fields.nth(2).fill(post_code)
        return self._click_submit_with_dialog("(//button[normalize-space()='Add Customer'])[last()]")

    def open_account(self, customer_name: str, currency: str) -> str:
        self.open_manager_tab("Open Account")
        self.page.locator("#userSelect").select_option(label=customer_name)
        self.page.locator("#currency").select_option(value=currency)
        return self._click_submit_with_dialog("button:has-text('Process')")

    def go_to_deposit(self):
        self.click_button_contains("Deposit")
        self.page.wait_for_selector("text=Amount to be Deposited")

    def go_to_withdraw(self):
        self.click_button_contains("Withdrawl")
        self.page.wait_for_selector("text=Amount to be Withdrawn")

    def go_to_transactions(self):
        self.click_button_contains("Transactions")
        self.page.wait_for_selector("text=Date-Time")

    def amount_input(self):
        return self.page.locator(AMOUNT_INPUT)

    def form_fields(self):
        return self.page.locator(FORM_CONTROL)

    def is_invalid(self, locator) -> bool:
        return locator.evaluate("el => el.checkValidity()") is False

    def input_amount(self, amount):
        self.amount_input().fill(str(amount))

    def submit_deposit(self):
        self.page.locator("(//button[normalize-space()='Deposit'])[last()]").click()

    def submit_withdraw(self):
        self.page.locator("(//button[normalize-space()='Withdraw'])[last()]").click()

    def transaction_rows(self):
        return self.page.locator("tbody tr")

    def customer_rows(self):
        return self.page.locator("tbody tr")