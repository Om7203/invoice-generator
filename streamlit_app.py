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
from decimal import Decimal
from zoneinfo import ZoneInfo

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

    def invoices(self, start=None, end=None):
        fields = "id,invoice_no,invoice_date,buyer_name,gstin,hsn,sub_desc,qty,rate,taxable,cgst,sgst,round_off,total,created_at"
        if self.remote:
            rows = []
            offset = 0
            while True:
                query = self.client.table("invoices").select(fields).order("invoice_date", desc=True).order("id", desc=True)
                if start:
                    query = query.gte("invoice_date", start)
                if end:
                    query = query.lt("invoice_date", end)
                batch = query.range(offset, offset + 499).execute().data or []
                if not batch:
                    return rows
                rows.extend(batch)
                offset += len(batch)
        conn = local_connection()
        conditions, params = [], []
        if start:
            conditions.append("invoice_date >= ?")
            params.append(start)
        if end:
            conditions.append("invoice_date < ?")
            params.append(end)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        rows = [dict(row) for row in conn.execute("SELECT " + fields + " FROM invoices" + where + " ORDER BY invoice_date DESC, id DESC", params)]
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
      body {{ margin:0; padding:10px; box-sizing:border-box; border-radius:12px; background:#1C2A38; color:#EDF4F8; font-family:Arial,sans-serif; }}
      button {{ border:0; border-radius:10px; padding:12px 14px; background:#45D0C1; color:#101923; font-size:14px; font-weight:700; cursor:pointer; min-height:48px; }}
      button:focus-visible, a:focus-visible {{ outline:3px solid #EDF4F8; outline-offset:3px; }}
      a {{ display:none; margin-left:8px; color:#70E0D4; }}
      #status {{ margin-top:8px; font-size:13px; line-height:1.5; color:#EDF4F8; }}
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
    components.html(html_block, height=160, scrolling=True)


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


def customer_form(store, language, expanded=False):
    with st.expander("＋ " + t("add_customer", language), expanded=expanded):
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
                    st.session_state.selected_customer = customer["name"]
                    st.session_state.customer_saved = True
                    st.rerun()


def monthly_totals(rows):
    """Aggregate saved invoice values without recalculating historic tax/rates."""
    totals = {key: Decimal("0") for key in ("qty", "taxable", "cgst", "sgst", "total")}
    customers = {}
    for row in rows:
        identity = (row["buyer_name"], row["gstin"])
        customer = customers.setdefault(identity, {"Customer": identity[0], "GSTIN": identity[1], "Invoices": 0, "Meters": Decimal("0"), "Total billed (INR)": Decimal("0")})
        customer["Invoices"] += 1
        customer["Meters"] += Decimal(str(row["qty"]))
        customer["Total billed (INR)"] += Decimal(str(row["total"]))
        for key in totals:
            totals[key] += Decimal(str(row[key]))
    return totals, [customers[key] for key in sorted(customers)]


def monthly_report(store, language):
    gu = language == "gu"
    st.header("માસિક રિપોર્ટ" if gu else "Monthly report")
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    left, right = st.columns(2)
    with left:
        year = int(st.number_input("વર્ષ" if gu else "Year", min_value=1900, max_value=9998, value=today.year, step=1))
    with right:
        month = st.selectbox("મહિનો" if gu else "Month", list(range(1, 13)), index=today.month - 1,
                             format_func=lambda m: date(2000, m, 1).strftime("%m — %B"))
    start = date(year, month, 1)
    end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    rows = store.invoices(start.isoformat(), end.isoformat())
    totals, customers = monthly_totals(rows)
    st.caption("ઇન્વોઇસની તારીખ પ્રમાણે રિપોર્ટ. કુલ રકમમાં ટેક્સ સામેલ છે." if gu else
               "Based on invoice date, including backdated invoices. Total billed includes tax and round-off.")
    a, b, c = st.columns(3)
    a.metric("કુલ બિલ" if gu else "Total billed", "₹ " + money(totals["total"]))
    b.metric("કુલ મીટર" if gu else "Total meters", money(totals["qty"]))
    c.metric("ઇન્વોઇસની સંખ્યા" if gu else "Invoice count", len(rows))
    st.caption(("કરપાત્ર રકમ" if gu else "Taxable value") + f": ₹ {money(totals['taxable'])} · CGST: ₹ {money(totals['cgst'])} · SGST: ₹ {money(totals['sgst'])}")
    if not rows:
        st.info("આ મહિનામાં કોઈ ઇન્વોઇસ નથી." if gu else "No invoices for this month.")
        return
    st.subheader("ગ્રાહક પ્રમાણે કુલ" if gu else "Customer totals")
    st.dataframe([{k: float(v) if isinstance(v, Decimal) else v for k, v in row.items()} for row in customers], hide_index=True, use_container_width=True)
    st.subheader("મહિનાના બધા ઇન્વોઇસ" if gu else "All invoices this month")
    labels = {"invoice_no": "Invoice", "invoice_date": "Date", "buyer_name": "Customer", "sub_desc": "Description", "qty": "Meters", "rate": "Rate", "total": "Total billed (INR)"}
    st.dataframe([{label: row[key] for key, label in labels.items()} for row in rows], hide_index=True, use_container_width=True)
    st.download_button("માસિક એક્સેલ લેજર" if gu else "Download monthly Excel ledger",
                       export_xlsx(rows), f"Sales_Ledger_{year}-{month:02d}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)


def main():
    st.set_page_config(page_title="Pure Invoice Generator", page_icon="🧾", layout="centered")
    st.markdown("""<style>
      .block-container {max-width:850px; padding-top:2rem;}
      div[data-testid="stVerticalBlockBorderWrapper"] {border-radius:16px;}
      div.stButton > button, div.stDownloadButton > button {min-height:52px; border-radius:12px; font-weight:600;}
      input {font-size:18px !important;}
      @media(max-width:600px) {.block-container {padding:1rem;}}
    </style>""", unsafe_allow_html=True)
    language = st.radio("Language / ભાષા", ["en", "gu"], horizontal=True,
                        format_func=lambda value: "English" if value == "en" else "ગુજરાતી",
                        key="language")
    if not login_gate(language):
        return

    store = Store()
    if st.session_state.pop("reset_entry", False):
        st.session_state.entry_invoice_no = store.next_invoice_number()
        st.session_state.entry_qty = 1.0
        st.session_state.entry_date = date.today()
    st.title(t("title", language))
    st.caption("ગ્રાહક પસંદ કરો → જથ્થો દાખલ કરો → PDF બનાવો" if language == "gu" else
               "Choose customer → Enter quantity → Create PDF")
    page = st.radio("મેનુ" if language == "gu" else "Menu", ["new", "history", "monthly"],
                    format_func=lambda value: ("માસિક રિપોર્ટ" if language == "gu" else "Monthly report") if value == "monthly" else t(value, language), horizontal=True, key="page")
    if page == "monthly":
        monthly_report(store, language)
        return
    if page == "history":
        st.header(t("history", language))
        rows = store.invoices()
        if not rows:
            st.info("હજુ કોઈ ઇન્વોઇસ નથી." if language == "gu" else "No invoices yet.")
        page_count = max(1, (len(rows) + 19) // 20)
        history_page = int(st.number_input("પાનું" if language == "gu" else "Page", min_value=1, max_value=page_count, value=1, step=1))
        for row in rows[(history_page - 1) * 20:history_page * 20]:
            with st.expander(f"Invoice {row['invoice_no']} · {row['buyer_name']} · ₹ {money(row['total'])}"):
                st.write(f"{row['invoice_date']} · {row['sub_desc']} · {row['qty']:,.2f} MTR")
                pdf_bytes = store.pdf(row["id"])
                st.download_button(t("download", language), pdf_bytes, f"Invoice_{safe_filename(row['invoice_no'])}.pdf", "application/pdf", key=f"history-download-{row['id']}")
        if rows:
            st.download_button(t("export", language), export_xlsx(rows), "Master_Sales_Ledger.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        return

    if st.session_state.pop("customer_saved", False):
        st.success("ગ્રાહક સાચવાયો." if language == "gu" else "Customer saved and selected.")
    st.subheader(t("new", language))
    if "entry_invoice_no" not in st.session_state:
        st.session_state.entry_invoice_no = store.next_invoice_number()
    col1, col2 = st.columns(2)
    with col1:
        invoice_no = st.text_input(t("invoice_no", language), key="entry_invoice_no")
    with col2:
        invoice_date = st.date_input(t("invoice_date", language), value=date.today(), key="entry_date")
    qty = st.number_input(t("quantity", language), min_value=0.01, value=1.0, step=0.01, key="entry_qty")
    st.caption("ફક્ત નંબર, તારીખ અને મીટર દાખલ કરો. પછી ગ્રાહક અને વિગત પસંદ કરો." if language == "gu" else
               "Enter only the invoice number, date and meters. Then choose the customer and description; the price is automatic.")
    customers = store.customers()
    if not customers:
        st.info("હજુ ગ્રાહકો ઉમેરાયા નથી. જૂના ગ્રાહકો આયાત કરો અથવા નીચે નવો ગ્રાહક ઉમેરો." if language == "gu" else "No saved customers yet. Import your existing customers into the database once, or add a new customer below.")
        customer_form(store, language, expanded=True)
        return
    names = [item["name"] for item in customers]
    if st.session_state.get("customer_choice") not in names:
        st.session_state.customer_choice = names[0]
    if st.session_state.get("selected_customer") in names:
        st.session_state.customer_choice = st.session_state.pop("selected_customer")
    with st.container(border=True):
        selected_name = st.selectbox(t("choose_customer", language), names, key="customer_choice")
    customer = next(item for item in customers if item["name"] == selected_name)
    descriptions = customer.get("descriptions", [])
    if not descriptions:
        st.warning("This customer has no saved descriptions.")
        customer_form(store, language)
        return
    rates = customer.get("description_rates", {})
    selected_description = st.selectbox(t("description", language), descriptions, key="description-" + selected_name)
    rate = float(rates.get(selected_description, customer.get("default_rate", 0)))
    st.metric(t("rate", language), f"₹ {money(rate)}")
    taxable = round(qty * rate, 2)
    cgst = round(taxable * 0.025, 2)
    sgst = round(taxable * 0.025, 2)
    total = round(taxable + cgst + sgst)
    round_off = round(total - taxable - cgst - sgst, 2)
    st.metric(t("total", language), f"₹ {money(total)}")

    if st.button(t("create", language), type="primary", use_container_width=True):
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
            st.session_state.last_invoice = (invoice_id, invoice_no, pdf_bytes, filename)

    if "last_invoice" in st.session_state:
        invoice_id, saved_no, pdf_bytes, filename = st.session_state.last_invoice
        with st.container(border=True):
            st.success(f"ઇન્વોઇસ {saved_no} સાચવાયું." if language == "gu" else f"Invoice {saved_no} saved. Your PDF is ready.")
            st.download_button(t("download", language), pdf_bytes, filename, "application/pdf", key=f"download-{invoice_id}", use_container_width=True)
            share_component(pdf_bytes, filename, saved_no, language)
            if st.button(t("new", language), use_container_width=True):
                st.session_state.pop("last_invoice", None)
                # Widget values are reset on the next run, before widgets are created.
                st.session_state.reset_entry = True
                st.rerun()
    customer_form(store, language)


if __name__ == "__main__":
    main()
