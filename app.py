import io
from datetime import datetime, date
import pandas as pd
import mysql.connector
from mysql.connector import Error
import streamlit as st
DB_CONFIG = {
    "host": "localhost",
    "user": "haaroon",
    "password": "Ah777#sql",
    "database": "banking_system",
}
def create_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        st.error(f"Database connection failed: {e}")
        return None
def create_tables():
    connection = create_connection()
    if connection is None:
        return
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                account_no VARCHAR(20) PRIMARY KEY,
                account_holder VARCHAR(100) NOT NULL,
                phone VARCHAR(15) NOT NULL,
                address VARCHAR(255),
                document_no VARCHAR(50),
                account_type VARCHAR(20) NOT NULL,
                balance DECIMAL(15, 2) NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                account_no VARCHAR(20) NOT NULL,
                transaction_type VARCHAR(20) NOT NULL,
                amount DECIMAL(15, 2) NOT NULL,
                receiver_account VARCHAR(20),
                timestamp DATETIME NOT NULL,
                FOREIGN KEY (account_no) REFERENCES accounts(account_no)
                    ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS loan_requests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                account_no VARCHAR(20) NOT NULL,
                amount DECIMAL(15, 2) NOT NULL,
                repayment_period INT NOT NULL,
                collateral VARCHAR(255),
                status VARCHAR(20) NOT NULL DEFAULT 'Pending',
                FOREIGN KEY (account_no) REFERENCES accounts(account_no)
                    ON DELETE CASCADE
            )
        """)
        connection.commit()
    except Error as e:
        st.error(f"Error creating tables: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
def run_query(query, params=None, fetch=False, fetch_one=False):
    connection = create_connection()
    if connection is None:
        return None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, params or ())
        if fetch_one:
            result = cursor.fetchone()
            return result
        if fetch:
            result = cursor.fetchall()
            return result
        connection.commit()
        return True
    except Error as e:
        st.error(f"Database error: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
def account_exists(account_no):
    result = run_query(
        "SELECT account_no FROM accounts WHERE account_no = %s",
        (account_no,),
        fetch_one=True,
    )
    return result is not None
def get_account(account_no):
    return run_query(
        "SELECT * FROM accounts WHERE account_no = %s",
        (account_no,),
        fetch_one=True,
    )
def get_all_account_numbers():
    rows = run_query("SELECT account_no FROM accounts ORDER BY account_no", fetch=True)
    return [row["account_no"] for row in rows] if rows else []
def record_transaction(cursor, account_no, transaction_type, amount, receiver_account=None):
    cursor.execute(
        """
        INSERT INTO transactions (account_no, transaction_type, amount, receiver_account, timestamp)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (account_no, transaction_type, amount, receiver_account, datetime.now()),
    )
def create_account(account_no, holder, phone, address, document_no, account_type, initial_deposit):
    if account_exists(account_no):
        return False, "Account number already exists. Please choose a different one."
    result = run_query(
        """
        INSERT INTO accounts (account_no, account_holder, phone, address,
                               document_no, account_type, balance, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (account_no, holder, phone, address, document_no, account_type,
         initial_deposit, datetime.now()),
    )
    if result:
        return True, "Account created successfully."
    return False, "Failed to create account."
def deposit_money(account_no, amount):
    if not account_exists(account_no):
        return False, "Account does not exist."
    if amount <= 0:
        return False, "Deposit amount must be greater than zero."
    connection = create_connection()
    if connection is None:
        return False, "Database connection error."
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE accounts SET balance = balance + %s WHERE account_no = %s",
            (amount, account_no),
        )
        record_transaction(cursor, account_no, "Deposit", amount)
        connection.commit()
        return True, f"Deposited {amount:.2f} successfully."
    except Error as e:
        connection.rollback()
        return False, f"Deposit failed: {e}"
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
def withdraw_money(account_no, amount):
    account = get_account(account_no)
    if account is None:
        return False, "Account does not exist."
    if amount <= 0:
        return False, "Withdrawal amount must be greater than zero."
    if account["balance"] < amount:
        return False, "Insufficient balance for this withdrawal."
    connection = create_connection()
    if connection is None:
        return False, "Database connection error."
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE accounts SET balance = balance - %s WHERE account_no = %s",
            (amount, account_no),
        )
        record_transaction(cursor, account_no, "Withdraw", amount)
        connection.commit()
        return True, f"Withdrew {amount:.2f} successfully."
    except Error as e:
        connection.rollback()
        return False, f"Withdrawal failed: {e}"
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
def transfer_money(sender_account, receiver_account, amount):
    if sender_account == receiver_account:
        return False, "Sender and receiver accounts cannot be the same."
    sender = get_account(sender_account)
    receiver = get_account(receiver_account)
    if sender is None:
        return False, "Sender account does not exist."
    if receiver is None:
        return False, "Receiver account does not exist."
    if amount <= 0:
        return False, "Transfer amount must be greater than zero."
    if sender["balance"] < amount:
        return False, "Insufficient balance for this transfer."
    connection = create_connection()
    if connection is None:
        return False, "Database connection error."
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE accounts SET balance = balance - %s WHERE account_no = %s",
            (amount, sender_account),
        )
        cursor.execute(
            "UPDATE accounts SET balance = balance + %s WHERE account_no = %s",
            (amount, receiver_account),
        )
        record_transaction(cursor, sender_account, "Transfer", amount, receiver_account)
        record_transaction(cursor, receiver_account, "Deposit", amount, sender_account)
        connection.commit()
        return True, f"Transferred {amount:.2f} from {sender_account} to {receiver_account}."
    except Error as e:
        connection.rollback()
        return False, f"Transfer failed: {e}"
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
def request_loan(account_no, amount, repayment_period, collateral):
    if not account_exists(account_no):
        return False, "Account does not exist."
    if amount <= 0:
        return False, "Loan amount must be greater than zero."
    if repayment_period <= 0:
        return False, "Repayment period must be greater than zero."
    result = run_query(
        """
        INSERT INTO loan_requests (account_no, amount, repayment_period, collateral, status)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (account_no, amount, repayment_period, collateral, "Pending"),
    )
    if result:
        return True, "Loan request submitted successfully. Status: Pending."
    return False, "Failed to submit loan request."
def search_account(account_no):
    return get_account(account_no)
def update_account(account_no, phone, address, account_type):
    if not account_exists(account_no):
        return False, "Account does not exist."
    result = run_query(
        """
        UPDATE accounts
        SET phone = %s, address = %s, account_type = %s
        WHERE account_no = %s
        """,
        (phone, address, account_type, account_no),
    )
    if result:
        return True, "Account updated successfully."
    return False, "Failed to update account."
def delete_account(account_no):
    if not account_exists(account_no):
        return False, "Account does not exist."
    result = run_query("DELETE FROM accounts WHERE account_no = %s", (account_no,))
    if result:
        return True, "Account deleted successfully."
    return False, "Failed to delete account."
def get_dashboard_data():
    data = {
        "total_accounts": 0,
        "total_balance": 0.0,
        "total_deposits": 0.0,
        "total_withdrawals": 0.0,
        "recent_transactions": [],
    }
    accounts_summary = run_query(
        "SELECT COUNT(*) AS total_accounts, COALESCE(SUM(balance), 0) AS total_balance FROM accounts",
        fetch_one=True,
    )
    if accounts_summary:
        data["total_accounts"] = accounts_summary["total_accounts"]
        data["total_balance"] = float(accounts_summary["total_balance"])
    deposits_summary = run_query(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM transactions WHERE transaction_type = 'Deposit'",
        fetch_one=True,
    )
    if deposits_summary:
        data["total_deposits"] = float(deposits_summary["total"])
    withdrawals_summary = run_query(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM transactions WHERE transaction_type = 'Withdraw'",
        fetch_one=True,
    )
    if withdrawals_summary:
        data["total_withdrawals"] = float(withdrawals_summary["total"])
    recent = run_query(
        "SELECT * FROM transactions ORDER BY timestamp DESC LIMIT 10",
        fetch=True,
    )
    data["recent_transactions"] = recent or []
    return data
def get_transactions(account_no=None, transaction_type=None, start_date=None, end_date=None):
    query = "SELECT * FROM transactions WHERE 1=1"
    params = []
    if account_no:
        query += " AND account_no = %s"
        params.append(account_no)
    if transaction_type and transaction_type != "All":
        query += " AND transaction_type = %s"
        params.append(transaction_type)
    if start_date:
        query += " AND DATE(timestamp) >= %s"
        params.append(start_date)
    if end_date:
        query += " AND DATE(timestamp) <= %s"
        params.append(end_date)
    query += " ORDER BY timestamp DESC"
    rows = run_query(query, tuple(params), fetch=True)
    return rows or []
def get_all_accounts(name_filter=None, account_no_filter=None, sort_by_balance=False):
    query = "SELECT * FROM accounts WHERE 1=1"
    params = []
    if name_filter:
        query += " AND account_holder LIKE %s"
        params.append(f"%{name_filter}%")
    if account_no_filter:
        query += " AND account_no LIKE %s"
        params.append(f"%{account_no_filter}%")
    query += " ORDER BY balance DESC" if sort_by_balance else " ORDER BY created_at DESC"
    rows = run_query(query, tuple(params), fetch=True)
    return rows or []
def dataframe_to_csv_bytes(df):
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")
def page_dashboard():
    """Render the Dashboard page with summary metrics and recent activity."""
    st.title("🏦 Banking Management System")
    st.subheader("Dashboard")
    data = get_dashboard_data()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Accounts", data["total_accounts"])
    col2.metric("Total Balance", f"₹ {data['total_balance']:,.2f}")
    col3.metric("Total Deposits", f"₹ {data['total_deposits']:,.2f}")
    col4.metric("Total Withdrawals", f"₹ {data['total_withdrawals']:,.2f}")
    st.markdown("---")
    st.subheader("Recent Transactions")
    if data["recent_transactions"]:
        df = pd.DataFrame(data["recent_transactions"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No transactions recorded yet.")
def page_create_account():
    """Render the Create Account page with a form for new account details."""
    st.title("Create Account")
    with st.form("create_account_form", clear_on_submit=True):
        account_no = st.text_input("Account Number *")
        holder = st.text_input("Account Holder Name *")
        phone = st.text_input("Phone Number *")
        address = st.text_area("Address")
        document_no = st.text_input("Document Number (ID Proof)")
        account_type = st.selectbox("Account Type", ["Savings", "Current", "Fixed Deposit"])
        initial_deposit = st.number_input("Initial Deposit", min_value=0.0, step=100.0, format="%.2f")
        submitted = st.form_submit_button("Create Account")
        if submitted:
            if not account_no or not holder or not phone:
                st.warning("Please fill in all required fields (marked with *).")
            elif not phone.isdigit():
                st.warning("Phone number should contain digits only.")
            else:
                success, message = create_account(
                    account_no.strip(), holder.strip(), phone.strip(),
                    address.strip(), document_no.strip(), account_type, initial_deposit
                )
                if success:
                    st.success(message)
                else:
                    st.error(message)
def page_deposit():
    """Render the Deposit page allowing money to be added to an account."""
    st.title("Deposit Money")
    accounts = get_all_account_numbers()
    if not accounts:
        st.info("No accounts available. Please create an account first.")
        return
    with st.form("deposit_form"):
        account_no = st.selectbox("Select Account", accounts)
        amount = st.number_input("Deposit Amount", min_value=0.0, step=100.0, format="%.2f")
        submitted = st.form_submit_button("Deposit")
        if submitted:
            if amount <= 0:
                st.warning("Please enter a valid deposit amount.")
            else:
                success, message = deposit_money(account_no, amount)
                if success:
                    st.success(message)
                    account = get_account(account_no)
                    if account:
                        st.metric("New Balance", f"₹ {float(account['balance']):,.2f}")
                else:
                    st.error(message)
def page_withdraw():
    """Render the Withdraw page allowing money to be removed from an account."""
    st.title("Withdraw Money")
    accounts = get_all_account_numbers()
    if not accounts:
        st.info("No accounts available. Please create an account first.")
        return
    with st.form("withdraw_form"):
        account_no = st.selectbox("Select Account", accounts)
        amount = st.number_input("Withdrawal Amount", min_value=0.0, step=100.0, format="%.2f")
        submitted = st.form_submit_button("Withdraw")
        if submitted:
            if amount <= 0:
                st.warning("Please enter a valid withdrawal amount.")
            else:
                success, message = withdraw_money(account_no, amount)
                if success:
                    st.success(message)
                    account = get_account(account_no)
                    if account:
                        st.metric("New Balance", f"₹ {float(account['balance']):,.2f}")
                else:
                    st.error(message)
def page_transfer_funds():
    st.title("Transfer Funds")
    accounts = get_all_account_numbers()
    if len(accounts) < 2:
        st.info("At least two accounts are required to perform a transfer.")
        return
    with st.form("transfer_form"):
        sender_account = st.selectbox("Sender Account", accounts, key="sender")
        receiver_account = st.selectbox("Receiver Account", accounts, key="receiver")
        amount = st.number_input("Transfer Amount", min_value=0.0, step=100.0, format="%.2f")
        submitted = st.form_submit_button("Transfer")
        if submitted:
            if amount <= 0:
                st.warning("Please enter a valid transfer amount.")
            else:
                success, message = transfer_money(sender_account, receiver_account, amount)
                if success:
                    st.success(message)
                else:
                    st.error(message)
def page_loan_request():
    st.title("Loan Request")
    accounts = get_all_account_numbers()
    if not accounts:
        st.info("No accounts available. Please create an account first.")
        return
    with st.form("loan_form", clear_on_submit=True):
        account_no = st.selectbox("Account Number", accounts)
        amount = st.number_input("Loan Amount", min_value=0.0, step=1000.0, format="%.2f")
        repayment_period = st.number_input("Repayment Period (months)", min_value=1, step=1)
        collateral = st.text_area("Collateral Details")
        submitted = st.form_submit_button("Submit Loan Request")
        if submitted:
            success, message = request_loan(account_no, amount, int(repayment_period), collateral.strip())
            if success:
                st.success(message)
            else:
                st.error(message)
def page_search_account():
    st.title("Search Account")
    with st.form("search_form"):
        account_no = st.text_input("Enter Account Number")
        submitted = st.form_submit_button("Search")
        if submitted:
            if not account_no:
                st.warning("Please enter an account number to search.")
            else:
                account = search_account(account_no.strip())
                if account:
                    st.success("Account found.")
                    with st.expander("Account Details", expanded=True):
                        st.write(f"**Account Number:** {account['account_no']}")
                        st.write(f"**Account Holder:** {account['account_holder']}")
                        st.write(f"**Phone:** {account['phone']}")
                        st.write(f"**Address:** {account['address']}")
                        st.write(f"**Document No.:** {account['document_no']}")
                        st.write(f"**Account Type:** {account['account_type']}")
                        st.write(f"**Created At:** {account['created_at']}")
                        st.metric("Balance", f"₹ {float(account['balance']):,.2f}")
                else:
                    st.error("No account found with that account number.")
def page_update_account():
    st.title("Update Account")
    accounts = get_all_account_numbers()
    if not accounts:
        st.info("No accounts available. Please create an account first.")
        return
    account_no = st.selectbox("Select Account to Update", accounts)
    account = get_account(account_no)
    if account:
        with st.form("update_form"):
            phone = st.text_input("Phone Number", value=account["phone"])
            address = st.text_area("Address", value=account["address"] or "")
            account_type = st.selectbox(
                "Account Type",
                ["Savings", "Current", "Fixed Deposit"],
                index=["Savings", "Current", "Fixed Deposit"].index(account["account_type"])
                if account["account_type"] in ["Savings", "Current", "Fixed Deposit"] else 0,
            )
            submitted = st.form_submit_button("Save Changes")
            if submitted:
                if not phone:
                    st.warning("Phone number cannot be empty.")
                else:
                    success, message = update_account(account_no, phone.strip(), address.strip(), account_type)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
def page_delete_account():
    st.title("Delete Account")
    accounts = get_all_account_numbers()
    if not accounts:
        st.info("No accounts available to delete.")
        return
    account_no = st.selectbox("Select Account to Delete", accounts)
    account = get_account(account_no)
    if account:
        with st.expander("Account Details", expanded=True):
            st.write(f"**Account Holder:** {account['account_holder']}")
            st.write(f"**Balance:** ₹ {float(account['balance']):,.2f}")
        with st.form("delete_form"):
            confirm = st.checkbox("I confirm I want to permanently delete this account.")
            submitted = st.form_submit_button("Delete Account")
            if submitted:
                if not confirm:
                    st.warning("Please check the confirmation box before deleting.")
                else:
                    success, message = delete_account(account_no)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
def page_transaction_history():
    st.title("Transaction History")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        account_no = st.text_input("Filter by Account Number")
    with col2:
        transaction_type = st.selectbox("Filter by Type", ["All", "Deposit", "Withdraw", "Transfer"])
    with col3:
        start_date = st.date_input("Start Date", value=None)
    with col4:
        end_date = st.date_input("End Date", value=None)
    if st.button("Apply Filters"):
        st.session_state["history_filtered"] = True
    transactions = get_transactions(
        account_no=account_no.strip() if account_no else None,
        transaction_type=transaction_type,
        start_date=start_date if isinstance(start_date, date) else None,
        end_date=end_date if isinstance(end_date, date) else None,
    )
    if transactions:
        df = pd.DataFrame(transactions)
        st.dataframe(df, use_container_width=True)
        csv_bytes = dataframe_to_csv_bytes(df)
        st.download_button(
            "Download Transaction History as CSV",
            data=csv_bytes,
            file_name="transaction_history.csv",
            mime="text/csv",
        )
    else:
        st.info("No transactions found for the selected filters.")
def page_view_all_accounts():
    st.title("View All Accounts")
    col1, col2, col3 = st.columns(3)
    with col1:
        name_filter = st.text_input("Search by Name")
    with col2:
        account_no_filter = st.text_input("Search by Account Number")
    with col3:
        sort_by_balance = st.checkbox("Sort by Balance (High to Low)")
    accounts = get_all_accounts(
        name_filter=name_filter.strip() if name_filter else None,
        account_no_filter=account_no_filter.strip() if account_no_filter else None,
        sort_by_balance=sort_by_balance,
    )
    if accounts:
        df = pd.DataFrame(accounts)
        st.dataframe(df, use_container_width=True)

        csv_bytes = dataframe_to_csv_bytes(df)
        st.download_button(
            "Download Account List as CSV",
            data=csv_bytes,
            file_name="accounts_list.csv",
            mime="text/csv",
        )
    else:
        st.info("No accounts found.")
def main():
    st.set_page_config(page_title="Banking Management System", page_icon="🏦", layout="wide")
    create_tables()
    st.sidebar.title("🏦 Bank Menu")
    pages = {
        "Dashboard": page_dashboard,
        "Create Account": page_create_account,
        "Deposit": page_deposit,
        "Withdraw": page_withdraw,
        "Transfer Funds": page_transfer_funds,
        "Loan Request": page_loan_request,
        "Search Account": page_search_account,
        "Update Account": page_update_account,
        "Delete Account": page_delete_account,
        "Transaction History": page_transaction_history,
        "View All Accounts": page_view_all_accounts,
    }
    choice = st.sidebar.radio("Navigate", list(pages.keys()))
    pages[choice]()
if __name__ == "__main__":
    main()