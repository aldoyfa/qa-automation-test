import os
import re

import pytest
from playwright.sync_api import sync_playwright
from xyz_bank import XYZBank

@pytest.fixture(scope="session")
def browser():
    headless = os.getenv("HEADLESS", "0") == "1"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        yield browser
        browser.close()

@pytest.fixture
def page(browser, request):
    context = browser.new_context(viewport={"width": 1366, "height": 768})
    page = context.new_page()
    app = XYZBank(page, request.node.name)
    request.node.app = app
    app.reset()
    yield page
    try:
        app.storage("final_local_storage")
    finally:
        context.close()

def app(request) -> XYZBank:
    return request.node.app

def test_tc001(page, request):
    bank = app(request)
    bank.snap("landing_page")
    assert "XYZ Bank" in bank.text()
    assert page.get_by_role("button", name="Customer Login", exact=True).is_visible()
    assert page.get_by_role("button", name="Bank Manager Login", exact=True).is_visible()

def test_tc002(page, request):
    bank = app(request)
    bank.click_button("Customer Login")
    bank.snap("customer_login_form")
    page.locator("#userSelect").select_option(label="Hermoine Granger")
    bank.snap("customer_selected")
    bank.click_button("Login")
    page.locator("#accountSelect").wait_for()
    bank.snap("account_page")
    text = bank.text()
    assert "Welcome Hermoine Granger" in text
    assert "Account Number" in text
    assert "Balance" in text
    assert "Currency" in text

def test_tc003(page, request):
    bank = app(request)
    bank.click_button("Customer Login")
    page.locator("#userSelect").wait_for()
    bank.snap("customer_selection_empty")
    assert not page.get_by_role("button", name="Login", exact=True).is_visible()
    assert "Your Name" in bank.text()

def test_tc004(page, request):
    bank = app(request)
    bank.remove_local("CurrentUser")
    bank.remove_local("CurrentAccount")
    bank.storage("storage_without_current_user")
    page.evaluate("window.location.hash = '#/account'")
    page.wait_for_timeout(1000)
    bank.snap("direct_account_route")
    assert "Customer Login" in bank.text()
    assert "Welcome" not in bank.text()
    assert "{{user}}" not in bank.text()

def test_tc005(page, request):
    bank = app(request)
    bank.login_customer("Hermoine Granger")
    first_account = bank.current_account_no()
    page.locator("#accountSelect").select_option(index=1)
    bank.snap("second_account_selected")
    assert bank.current_account_no() != first_account
    assert "Currency" in bank.text()

def test_tc006(page, request):
    bank = app(request)
    alert_text = bank.add_customer("No", "Account", "NA001")
    assert "Customer added successfully" in alert_text
    bank.snap("new_customer_added")
    bank.go_home()
    bank.login_customer("No Account", expect_account=False)
    bank.snap("customer_without_account")
    assert "Please open an account with us." in bank.text()
    assert not page.locator("#accountSelect").is_visible()

def test_tc007(page, request):
    bank = app(request)
    bank.login_customer("Hermoine Granger")
    start_balance = bank.current_balance()
    bank.go_to_deposit()
    bank.input_amount(100)
    bank.snap("deposit_100_input")
    bank.submit_deposit()
    page.locator(".error", has_text="Deposit Successful").wait_for()
    bank.snap("deposit_success")
    assert bank.current_balance() == start_balance + 100
    bank.go_to_transactions()
    bank.snap("deposit_transaction")
    transactions = bank.local_json("Transaction")
    user = bank.local_json("CurrentUser")
    account = bank.local_json("CurrentAccount")
    txs = transactions[str(user["id"])][str(account["accountNo"])]
    assert any(str(tx["amount"]) == "100" and tx["type"] == "Credit" for tx in txs)

def test_tc008(page, request):
    bank = app(request)
    bank.login_customer("Hermoine Granger")
    bank.go_to_deposit()
    bank.snap("deposit_empty")
    assert bank.is_invalid(bank.amount_input())

def test_tc009(page, request):
    bank = app(request)
    bank.login_customer("Hermoine Granger")
    start_balance = bank.current_balance()
    bank.go_to_deposit()
    bank.input_amount(0)
    bank.submit_deposit()
    bank.snap("deposit_zero")
    assert bank.current_balance() == start_balance
    assert "Deposit Successful" not in bank.text()

def test_tc010(page, request):
    bank = app(request)
    bank.login_customer("Hermoine Granger")
    start_balance = bank.current_balance()
    bank.go_to_deposit()
    bank.input_amount(-100)
    bank.submit_deposit()
    bank.snap("deposit_negative")
    assert bank.current_balance() == start_balance
    assert "Deposit Successful" not in bank.text()

def test_tc011(page, request):
    bank = app(request)
    bank.login_customer("Hermoine Granger")
    start_balance = bank.current_balance()
    bank.go_to_deposit()
    bank.input_amount("10.50")
    bank.submit_deposit()
    bank.snap("deposit_decimal")
    assert bank.current_balance() == start_balance

def test_tc012(page, request):
    bank = app(request)
    bank.login_customer("Hermoine Granger")
    start_balance = bank.current_balance()
    bank.go_to_deposit()
    bank.input_amount("999999999999999999999")
    bank.submit_deposit()
    bank.snap("deposit_huge_number")
    assert bank.current_balance() == start_balance

def test_tc013(page, request):
    bank = app(request)
    bank.login_customer("Hermoine Granger")
    bank.go_to_deposit()
    bank.input_amount(200)
    bank.submit_deposit()
    page.locator(".error", has_text="Deposit Successful").wait_for()
    balance_after_deposit = bank.current_balance()
    bank.go_to_withdraw()
    bank.input_amount(50)
    bank.snap("withdraw_50_input")
    bank.submit_withdraw()
    page.locator(".error", has_text="Transaction successful").wait_for()
    bank.snap("withdraw_success")
    assert bank.current_balance() == balance_after_deposit - 50

def test_tc014(page, request):
    bank = app(request)
    bank.login_customer("Hermoine Granger")
    start_balance = bank.current_balance()
    bank.go_to_withdraw()
    bank.input_amount(999999)
    bank.snap("withdraw_over_balance_input")
    bank.submit_withdraw()
    page.locator(".error", has_text="Transaction Failed").wait_for()
    bank.snap("withdraw_over_balance_failed")
    assert bank.current_balance() == start_balance

def test_tc015(page, request):
    bank = app(request)
    bank.login_customer("Hermoine Granger")
    start_balance = bank.current_balance()
    bank.go_to_withdraw()
    bank.snap("withdraw_empty")
    assert bank.is_invalid(bank.amount_input())
    bank.input_amount(0)
    bank.submit_withdraw()
    bank.snap("withdraw_zero")
    assert bank.current_balance() == start_balance
    bank.input_amount(-1)
    bank.submit_withdraw()
    bank.snap("withdraw_negative")
    assert bank.current_balance() == start_balance

def test_tc016(page, request):
    bank = app(request)
    bank.login_customer("Hermoine Granger")
    bank.go_to_deposit()
    bank.input_amount(10)
    bank.submit_deposit()
    balance_after_deposit = bank.current_balance()
    bank.go_to_withdraw()
    bank.input_amount("1.25")
    bank.submit_withdraw()
    bank.snap("withdraw_decimal")
    assert bank.current_balance() == balance_after_deposit

def test_tc017(page, request):
    bank = app(request)
    bank.login_customer("Hermoine Granger")
    bank.go_to_transactions()
    bank.snap("transaction_history")
    assert "Date-Time" in bank.text()
    assert "Amount" in bank.text()
    assert "Transaction Type" in bank.text()
    assert bank.transaction_rows().count() > 0

def test_tc018(page, request):
    bank = app(request)
    bank.login_customer("Hermoine Granger")
    bank.go_to_transactions()
    rows_before = bank.transaction_rows().all_inner_texts()[:3]
    page.get_by_text("Date-Time").click()
    bank.snap("transactions_sorted")
    rows_after = bank.transaction_rows().all_inner_texts()[:3]
    assert rows_after
    assert rows_before != rows_after

def test_tc019(page, request):
    bank = app(request)
    bank.login_customer("Hermoine Granger")
    bank.go_to_transactions()
    rows_before = bank.transaction_rows().count()
    page.evaluate(
        """
        () => {
            const start = document.getElementById('start');
            const end = document.getElementById('end');
            start.value = '2015-01-01T00:00:00';
            end.value = '2015-01-28T00:00:00';
            start.dispatchEvent(new Event('input', {bubbles: true}));
            end.dispatchEvent(new Event('input', {bubbles: true}));
        }
        """
    )
    bank.snap("transactions_date_filtered")
    assert bank.transaction_rows().count() <= rows_before

def test_tc020(page, request):
    bank = app(request)
    bank.login_customer("Hermoine Granger")
    bank.go_to_transactions()
    assert bank.transaction_rows().count() > 0
    bank.snap("before_reset_transactions")
    bank.click_button("Reset")
    bank.snap("after_reset_transactions")
    assert bank.transaction_rows().count() == 0
    bank.click_button("Back")
    bank.snap("after_reset_balance")
    assert bank.current_balance() == 0

def test_tc021(page, request):
    bank = app(request)
    bank.open_manager()
    bank.snap("manager_page")
    text = bank.text()
    assert "Add Customer" in text
    assert "Open Account" in text
    assert "Customers" in text

def test_tc022(page, request):
    bank = app(request)
    alert_text = bank.add_customer("Aldoy", "Fauzan", "AF123")
    bank.snap("customer_added")
    assert "Customer added successfully" in alert_text
    bank.open_manager_tab("Customers")
    bank.snap("customer_list_with_aldoy")
    assert "Aldoy" in bank.text()
    assert "Fauzan" in bank.text()

def test_tc023(page, request):
    bank = app(request)
    bank.open_manager_tab("Add Customer")
    fields = bank.form_fields()
    bank.snap("add_customer_empty")
    assert all(bank.is_invalid(fields.nth(i)) for i in range(3))

def test_tc024(page, request):
    bank = app(request)
    alert_text = bank.add_customer("Hermoine", "Granger", "E859AB")
    bank.snap("duplicate_customer_alert")
    assert "duplicate" in alert_text.lower()

def test_tc025(page, request):
    bank = app(request)
    alert_text = bank.add_customer(" Aldoy ", " Fauzan ", " AF123 ")
    assert "Customer added successfully" in alert_text
    bank.open_manager_tab("Customers")
    bank.snap("customer_with_spaces")
    assert " Aldoy " not in bank.text()
    assert " Fauzan " not in bank.text()
    assert " AF123 " not in bank.text()

def test_tc026(page, request):
    bank = app(request)
    alert_text = bank.add_customer(
        "<script>alert(1)</script>",
        "Safe",
        "<img src=x onerror=alert(1)>",
    )
    assert "Customer added successfully" in alert_text
    bank.open_manager_tab("Customers")
    bank.snap("script_payload_rendered")
    assert "<script>" not in page.content().lower()

def test_tc027(page, request):
    bank = app(request)
    bank.add_customer("Account", "Owner", "AO123")
    alert_text = bank.open_account("Account Owner", "Dollar")
    bank.snap("account_created")
    assert "Account created successfully" in alert_text
    bank.open_manager_tab("Customers")
    bank.snap("new_account_in_customer_list")
    assert "Account" in bank.text()
    assert re.search(r"\b10\d{2,}\b", bank.text())

def test_tc028(page, request):
    bank = app(request)
    bank.open_manager_tab("Open Account")
    bank.snap("open_account_empty")
    assert bank.is_invalid(page.locator("#userSelect"))
    assert bank.is_invalid(page.locator("#currency"))

def test_tc029(page, request):
    bank = app(request)
    alert_text = bank.open_account("Hermoine Granger", "Dollar")
    bank.snap("duplicate_currency_account")
    assert "can not be opened" in alert_text.lower() or "duplicate" in alert_text.lower()

def test_tc030(page, request):
    bank = app(request)
    bank.open_manager_tab("Customers")
    search = page.locator("input[placeholder='Search Customer']")
    search.fill("Hermoine")
    bank.snap("search_hermoine")
    assert "Hermoine" in bank.text()
    assert "Granger" in bank.text()
    search.fill("ZZZ999")
    bank.snap("search_no_result")
    assert "Hermoine" not in bank.text()

def test_tc031(page, request):
    bank = app(request)
    bank.open_manager_tab("Customers")
    before = bank.customer_rows().all_inner_texts()
    page.get_by_text("First Name").click()
    bank.snap("sort_customer_first_name")
    after = bank.customer_rows().all_inner_texts()
    assert before != after

def test_tc032(page, request):
    bank = app(request)
    bank.add_customer("Delete", "Me", "DM123")
    bank.open_manager_tab("Customers")
    bank.snap("before_delete_customer")
    page.locator("//tr[td[normalize-space()='Delete'] and td[normalize-space()='Me']]//button").click()
    bank.snap("after_delete_customer")
    assert "Delete Me" not in bank.text()

def test_tc033(page, request):
    bank = app(request)
    bank.open_manager_tab("Customers")
    first_row_text = bank.customer_rows().first.inner_text()
    messages = []

    def dismiss_dialog(dialog):
        messages.append(dialog.message)
        dialog.dismiss()

    page.once("dialog", dismiss_dialog)
    bank.customer_rows().first.locator("button").click()
    page.wait_for_timeout(500)
    bank.snap("delete_without_confirmation")
    assert messages, "Confirmation dialog tidak muncul"
    message = messages[0]
    assert "confirm" in message.lower()
    assert first_row_text in bank.text()

def test_tc034(page, request):
    bank = app(request)
    bank.login_customer("Hermoine Granger")
    bank.snap("logged_in_before_logout")
    bank.click_button("Logout")
    bank.snap("after_logout")
    assert "Your Name" in bank.text()
    page.locator("#userSelect").select_option(label="Hermoine Granger")
    bank.click_button("Login")
    bank.go_home()
    bank.snap("after_home")
    assert "Customer Login" in bank.text()
    assert "Bank Manager Login" in bank.text()

def test_tc035(page, request):
    bank = app(request)
    bank.login_customer("Hermoine Granger")
    assert bank.current_account_no() == 1001
    original_balance = bank.current_balance()
    current_account = bank.require_local_json("CurrentAccount")
    assert current_account["accountNo"] == 1001
    current_account["amount"] = 999999
    bank.set_local_json("CurrentAccount", current_account)
    bank.storage("tampered_current_account_storage")
    page.reload()
    page.locator("#accountSelect").wait_for()
    bank.snap("after_storage_tampering")
    tampered_balance = bank.current_balance()
    bank.click_button("Logout")
    bank.snap("after_tampering_logout")
    assert tampered_balance == original_balance

def test_tc036(page, request):
    bank = app(request)
    page.evaluate("window.location.hash = '#/manager/addCust'")
    page.wait_for_timeout(1000)
    bank.snap("direct_manager_add_customer_route")
    assert "Add Customer" not in bank.text()
    assert "Customer Login" in bank.text()