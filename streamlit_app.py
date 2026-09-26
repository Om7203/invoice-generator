"""Mobile-friendly invoice generator.

The app uses Supabase when SUPABASE_URL and SUPABASE_SERVICE_KEY are present.
Without those secrets it runs locally with SQLite, which is useful for testing.
"""

import base64
import hashlib
import html
import io
import json
import os
import secrets
import sqlite3
import tempfile
from datetime import date, datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from invoice_pdf import build_invoice_pdf


APP_DIR = Path(__file__).resolve().parent
LOCAL_DIR = APP_DIR / "local_data"
LOCAL_DB = LOCAL_DIR / "invoice_generator.db"
LOCAL_CUSTOMERS = LOCAL_DIR / "customers.json"

EXAMPLE_CUSTOMERS = [
    {
        "name": "EXAMPLE CUSTOMER",
        "gstin": "GSTIN-PLACEHOLDER",
        "state": "Gujarat",
        "state_code": "24",
        "descriptions": ["EXAMPLE JOB WORK"],
        "description_rates": {"EXAMPLE JOB WORK": 1.0},
        "hsn": "998821",
        "default_rate": 1.0,
    }
]

TEXT = {
    "en": {
        "title": "Pure Invoice Generator",
        "subtitle": "Simple invoice entry for in-house use",
        "new": "New invoice",
        "history": "Invoice history",
        "settings": "Business settings",
        "customer": "Customer",
        "choose_customer": "Choose customer",
        "invoice_no": "Invoice number",
        "invoice_date": "Invoice date",
        "description": "Work / description",
        "quantity": "Quantity (meters)",
        "rate": "Rate per meter",
        "create": "Create English invoice",
        "total": "Total",
        "download": "Download PDF",
        "share": "Share PDF on WhatsApp",
        "add_customer": "Add new customer",
        "save_customer": "Save customer",
        "customer_name": "Customer name",
        "gstin": "GSTIN",
        "state": "State",
        "state_code": "State code",
        "hsn": "HSN/SAC",
        "description_rates": "Descriptions and rates",
        "description_help": "One per line: DESCRIPTION | RATE",
        "export": "Export Excel backup",
        "login": "Enter app PIN",
        "open": "Open app",
    },
    "gu": {
        "title": "ઇન્વોઇસ જનરેટર",
        "subtitle": "ઘરના વ્યવસાય માટે સરળ ઇન્વોઇસ",
        "new": "નવું ઇન્વોઇસ",
        "history": "ઇન્વોઇસ ઇતિહાસ",
        "settings": "વ્યવસાય સેટિંગ્સ",
        "customer": "ગ્રાહક",
        "choose_customer": "ગ્રાહક પસંદ કરો",
        "invoice_no": "ઇન્વોઇસ નંબર",
        "invoice_date": "ઇન્વોઇસ તારીખ",
        "description": "કામ / વિગત",
        "quantity": "જથ્થો (મીટર)",
        "rate": "મીટરનો દર",
        "create": "અંગ્રેજી ઇન્વોઇસ બનાવો",
        "total": "કુલ",
        "download": "PDF ડાઉનલોડ કરો",
        "share": "WhatsApp પર PDF શેર કરો",
        "add_customer": "નવો ગ્રાહક ઉમેરો",
        "save_customer": "ગ્રાહક સાચવો",
        "customer_name": "ગ્રાહકનું નામ",
        "gstin": "GSTIN",
        "state": "રાજ્ય",
        "state_code": "રાજ્ય કોડ",
        "hsn": "HSN/SAC",
        "description_rates": "વિગતો અને દર",
        "description_help": "દરેક લાઇન: વિગત | દર",
        "export": "એક્સેલ બેકઅપ",
        "login": "એપ PIN દાખલ કરો",
        "open": "એપ ખોલો",
    },
}


def cfg(name, default=""):
    """Read a Streamlit secret first and an environment variable second."""
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    return value if value not in (None, "") else os.getenv(name, default)


def t(key, language):
    return TEXT[language].get(key, TEXT["en"].get(key, key))


def money(value):
    return f"{float(value):,.2f}"


def safe_filename(value):
    return "".join(char for char in str(value) if char.isalnum() or char in " -_").strip().replace(" ", "_")


def parse_description_rates(raw, default_rate):
    descriptions = []
    rates = {}
    for line in raw.replace(",", "\n").splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            label, rate_text = [part.strip() for part in line.split("|", 1)]
            try:
                rate = float(rate_text)
            except ValueError:
                rate = default_rate
        else:
            label, rate = line, default_rate
        label = label.upper()
        if label and label not in rates:
            descriptions.append(label)
            rates[label] = rate
    return descriptions, rates


def local_connection():
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT NOT NULL UNIQUE,
            invoice_date TEXT NOT NULL,
            buyer_name TEXT NOT NULL,
            gstin TEXT NOT NULL,
            hsn TEXT NOT NULL,
            sub_desc TEXT NOT NULL,
            qty REAL NOT NULL,
            rate REAL NOT NULL,
            taxable REAL NOT NULL,
            cgst REAL NOT NULL,
            sgst REAL NOT NULL,
            round_off REAL NOT NULL,
            total REAL NOT NULL,
            pdf_base64 TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    conn.commit()
    return conn


class Store:
    def __init__(self):
        self.url = cfg("SUPABASE_URL")
        self.key = cfg("SUPABASE_SERVICE_KEY")
        self.remote = bool(self.url and self.key)
        self.client = None
        if self.remote:
            from supabase import create_client

            self.client = create_client(self.url, self.key)

    def customers(self):
        if self.remote:
            response = self.client.table("customers").select("*").order("name").execute()
            return response.data or []
        if not LOCAL_CUSTOMERS.exists():
            LOCAL_CUSTOMERS.write_text(json.dumps(EXAMPLE_CUSTOMERS, indent=2), encoding="utf-8")
        return json.loads(LOCAL_CUSTOMERS.read_text(encoding="utf-8"))

    def save_customer(self, customer):
        if self.remote:
            self.client.table("customers").insert(customer).execute()
            return
        customers = self.customers()
        customers.append(customer)
        customers.sort(key=lambda item: item["name"])
        LOCAL_CUSTOMERS.write_text(json.dumps(customers, indent=2), encoding="utf-8")

    def invoice_exists(self, invoice_no):
        if self.remote:
            response = self.client.table("invoices").select("id").eq("invoice_no", invoice_no).limit(1).execute()
            return bool(response.data)
        conn = local_connection()
        found = conn.execute("SELECT id FROM invoices WHERE invoice_no = ?", (invoice_no,)).fetchone()
        conn.close()
        return found is not None

    def next_invoice_number(self):
        if self.remote:
            response = self.client.table("invoices").select("invoice_no").execute()
            values = [row["invoice_no"] for row in (response.data or [])]
        else:
            conn = local_connection()
            values = [row[0] for row in conn.execute("SELECT invoice_no FROM invoices")]
            conn.close()
        numeric = [int(value) for value in values if str(value).isdigit()]
        return str(max(numeric, default=0) + 1)

    def save_invoice(self, record):
        if self.remote:
            response = self.client.table("invoices").insert(record).execute()
            return (response.data or [{"id": record["invoice_no"]}])[0]["id"]
        conn = local_connection()
        cursor = conn.execute(
            """INSERT INTO invoices
            (invoice_no, invoice_date, buyer_name, gstin, hsn, sub_desc, qty, rate,
             taxable, cgst, sgst, round_off, total, pdf_base64, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            tuple(record[key] for key in (
                "invoice_no", "invoice_date", "buyer_name", "gstin", "hsn", "sub_desc",
                "qty", "rate", "taxable", "cgst", "sgst", "round_off", "total",
                "pdf_base64", "created_at"
            )),
        )
        conn.commit()
        row_id = cursor.lastrowid
        conn.close()
        return row_id

    def invoices(self):
        fields = "id,invoice_no,invoice_date,buyer_name,gstin,hsn,sub_desc,qty,rate,taxable,cgst,sgst,round_off,total,created_at"
        if self.remote:
            return self.client.table("invoices").select(fields).order("invoice_date", desc=True).limit(100).execute().data or []
        conn = local_connection()
        rows = [dict(row) for row in conn.execute("SELECT " + fields + " FROM invoices ORDER BY invoice_date DESC, id DESC LIMIT 100")]
        conn.close()
        return rows

    def pdf(self, invoice_id):
        if self.remote:
            response = self.client.table("invoices").select("pdf_base64").eq("id", invoice_id).single().execute()
            return base64.b64decode(response.data["pdf_base64"])
        conn = local_connection()
        row = conn.execute("SELECT pdf_base64 FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        conn.close()
        return base64.b64decode(row[0])


def seller_settings():
    return {
        "name": cfg("INVOICE_SELLER_NAME", "YOUR BUSINESS NAME"),
        "address_1": cfg("INVOICE_SELLER_ADDRESS_1", "YOUR ADDRESS LINE 1"),
        "address_2": cfg("INVOICE_SELLER_ADDRESS_2", "YOUR ADDRESS LINE 2"),
        "address_3": cfg("INVOICE_SELLER_ADDRESS_3", "YOUR CITY - PINCODE"),
        "gstin": cfg("INVOICE_SELLER_GSTIN", "YOUR GSTIN"),
        "state": cfg("INVOICE_SELLER_STATE", "Gujarat"),
        "state_code": cfg("INVOICE_SELLER_STATE_CODE", "24"),
    }


def make_pdf(record, customer):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp:
        temp_path = Path(temp.name)
    try:
        build_invoice_pdf(
            temp_path,
            record["invoice_no"],
            datetime.strptime(record["invoice_date"], "%Y-%m-%d").strftime("%d-%b-%y"),
            record["buyer_name"],
            record["gstin"],
            record["hsn"],
            record["sub_desc"],
            record["qty"],
            record["rate"],
            record["taxable"],
            record["cgst"],
            record["sgst"],
            record["round_off"],
            record["total"],
            customer.get("state", "Gujarat"),
            customer.get("state_code", "24"),
            seller=seller_settings(),
        )
        return temp_path.read_bytes()
    finally:
        temp_path.unlink(missing_ok=True)


def share_component(pdf_bytes, filename, invoice_no, language):
    filename = safe_filename(filename.removesuffix('.pdf')) + '.pdf'
    invoice_no = safe_filename(invoice_no)
    encoded = base64.b64encode(pdf_bytes).decode("ascii")
    button_label = html.escape(t("share", language))
    fallback = html.escape(t("download", language))
    html_block = f"""
    <style>
      body {{ margin:0; font-family:Arial,sans-serif; }}
      button {{ border:0; border-radius:10px; padding:11px 14px; background:#159a9c; color:#fff; font-size:14px; font-weight:700; cursor:pointer; }}
      a {{ display:none; margin-left:8px; color:#1e3d59; }}
      #status {{ margin-top:8px; font-size:12px; color:#64748b; }}
    </style>
    <button id="share">{button_label}</button><a id="fallback" download="{html.escape(filename)}">{fallback}</a>
    <div id="status"></div>
    <script>
      const raw = atob("{encoded}");
      const bytes = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
      const blob = new Blob([bytes], {{type: "application/pdf"}});
      const file = new File([blob], "{html.escape(filename)}", {{type: "application/pdf"}});
      const url = URL.createObjectURL(blob);
      document.getElementById("fallback").href = url;
      document.getElementById("share").addEventListener("click", async () => {{
        const status = document.getElementById("status");
        try {{
          if (navigator.share && navigator.canShare && navigator.canShare({{files:[file]}})) {{
            await navigator.share({{files:[file], title:"Invoice {html.escape(str(invoice_no))}", text:"Invoice {html.escape(str(invoice_no))}"}});
            status.textContent = "PDF shared successfully.";
          }} else {{
            document.getElementById("fallback").style.display = "inline";
            status.textContent = "Direct file sharing is not available on this browser. Download the PDF and attach it in WhatsApp.";
          }}
        }} catch (error) {{
          if (error.name !== "AbortError") {{
            document.getElementById("fallback").style.display = "inline";
            status.textContent = "Download the PDF and attach it in WhatsApp.";
          }}
        }}
      }});
    </script>
    """
    components.html(html_block, height=76)


def export_xlsx(rows):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Invoices"
    headers = ["Invoice No", "Date", "Buyer Name", "GSTIN", "HSN/SAC", "Sub-Description", "Quantity", "Rate", "Taxable Value", "CGST", "SGST", "Round Off", "Grand Total", "Created At"]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    keys = ["invoice_no", "invoice_date", "buyer_name", "gstin", "hsn", "sub_desc", "qty", "rate", "taxable", "cgst", "sgst", "round_off", "total", "created_at"]
    for row in rows:
        sheet.append([row.get(key, "") for key in keys])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for index, width in enumerate([14, 14, 24, 20, 12, 26, 14, 12, 16, 12, 12, 12, 14, 22], start=1):
        sheet.column_dimensions[chr(64 + index)].width = width
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def login_gate(language):
    pin = str(cfg("APP_PIN", ""))
    if not pin:
        st.error("Set APP_PIN in Streamlit Secrets before using this app.")
        return False
    if st.session_state.get("authenticated"):
        return True
    st.title(t("title", language))
    entered = st.text_input(t("login", language), type="password")
    if st.button(t("open", language), type="primary"):
        if secrets.compare_digest(entered, pin):
            st.session_state.authenticated = True
            st.rerun()
        st.error("Incorrect PIN.")
    return False


def main():
    st.set_page_config(page_title="Pure Invoice Generator", page_icon="🧾", layout="centered")
    language = st.sidebar.selectbox("Language / ભાષા", ["en", "gu"], format_func=lambda value: "English" if value == "en" else "ગુજરાતી")
    if not login_gate(language):
        return

    store = Store()
    st.title(t("title", language))
    st.caption(t("subtitle", language))
    page = st.sidebar.radio("Menu", [t("new", language), t("history", language), t("add_customer", language)])

    if page == t("history", language):
        st.header(t("history", language))
        rows = store.invoices()
        if not rows:
            st.info("No invoices yet.")
        else:
            for row in rows:
                with st.expander(f"Invoice {row['invoice_no']} · {row['buyer_name']} · ₹ {money(row['total'])}"):
                    st.write(f"{row['invoice_date']} · {row['sub_desc']} · {row['qty']:,.2f} MTR")
                    pdf_bytes = store.pdf(row["id"])
                    st.download_button(t("download", language), pdf_bytes, f"Invoice_{row['invoice_no']}.pdf", "application/pdf", key=f"history-download-{row['id']}")
        if rows:
            st.download_button(t("export", language), export_xlsx(rows), "Master_Sales_Ledger.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        return

    if page == t("add_customer", language):
        st.header(t("add_customer", language))
        with st.form("customer-form"):
            name = st.text_input(t("customer_name", language))
            gstin = st.text_input(t("gstin", language))
            state = st.text_input(t("state", language), value="Gujarat")
            state_code = st.text_input(t("state_code", language), value="24")
            hsn = st.text_input(t("hsn", language), value="998821")
            default_rate = st.number_input(t("rate", language), min_value=0.0, value=0.0, step=0.01)
            raw = st.text_area(t("description_rates", language), placeholder="ROTO - 60 | 4.05\nROTO - 60 BLACK | 4.10")
            st.caption(t("description_help", language))
            submitted = st.form_submit_button(t("save_customer", language), type="primary")
        if submitted:
            descriptions, rates = parse_description_rates(raw, default_rate)
            if not name.strip() or not gstin.strip() or not descriptions:
                st.error("Enter name, GSTIN, and at least one description.")
            else:
                existing = store.customers()
                if any(item["name"] == name.strip().upper() or item["gstin"] == gstin.strip().upper() for item in existing):
                    st.error("This customer or GSTIN already exists.")
                else:
                    customer = {"name": name.strip().upper(), "gstin": gstin.strip().upper(), "state": state.strip() or "Gujarat", "state_code": state_code.strip() or "24", "hsn": hsn.strip() or "998821", "descriptions": descriptions, "description_rates": rates, "default_rate": default_rate}
                    store.save_customer(customer)
                    st.success("Customer saved.")
        return

    st.header(t("new", language))
    customers = store.customers()
    if not customers:
        st.info("Add your first customer using the menu.")
        return
    names = [item["name"] for item in customers]
    selected_name = st.selectbox(t("choose_customer", language), names)
    customer = next(item for item in customers if item["name"] == selected_name)
    descriptions = customer.get("descriptions", [])
    rates = customer.get("description_rates", {})
    selected_description = st.selectbox(t("description", language), descriptions)
    default_rate = float(rates.get(selected_description, customer.get("default_rate", 0)))
    col1, col2 = st.columns(2)
    with col1:
        invoice_no = st.text_input(t("invoice_no", language), value=store.next_invoice_number())
        qty = st.number_input(t("quantity", language), min_value=0.01, value=1.0, step=0.01)
    with col2:
        invoice_date = st.date_input(t("invoice_date", language), value=date.today())
        rate = st.number_input(t("rate", language), min_value=0.0, value=default_rate, step=0.01)
    taxable = round(qty * rate, 2)
    cgst = round(taxable * 0.025, 2)
    sgst = round(taxable * 0.025, 2)
    total = round(taxable + cgst + sgst)
    round_off = round(total - taxable - cgst - sgst, 2)
    st.metric(t("total", language), f"₹ {money(total)}")

    if st.button(t("create", language), type="primary"):
        invoice_no = invoice_no.strip()
        if not invoice_no:
            st.error("Enter an invoice number.")
        elif store.invoice_exists(invoice_no):
            st.error(f"Invoice number {invoice_no} already exists.")
        else:
            record = {"invoice_no": invoice_no, "invoice_date": invoice_date.isoformat(), "buyer_name": customer["name"], "gstin": customer["gstin"], "hsn": customer.get("hsn", "998821"), "sub_desc": selected_description, "qty": qty, "rate": rate, "taxable": taxable, "cgst": cgst, "sgst": sgst, "round_off": round_off, "total": total, "created_at": datetime.now().isoformat(timespec="seconds")}
            pdf_bytes = make_pdf(record, customer)
            record["pdf_base64"] = base64.b64encode(pdf_bytes).decode("ascii")
            invoice_id = store.save_invoice(record)
            filename = f"{safe_filename(customer['name'])}_{safe_filename(invoice_no)}_{invoice_date.strftime('%d-%b-%y')}.pdf"
            st.success(f"Invoice {invoice_no} saved successfully.")
            st.download_button(t("download", language), pdf_bytes, filename, "application/pdf", key=f"download-{invoice_id}")
            share_component(pdf_bytes, filename, invoice_no, language)


if __name__ == "__main__":
    main()
