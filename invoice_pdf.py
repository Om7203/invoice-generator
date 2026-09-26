import os

from fpdf import FPDF


def num_to_words_inr(num):
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
            "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def convert_group(n):
        if n == 0:
            return ""
        if n < 20:
            return ones[n] + " "
        if n < 100:
            return tens[n // 10] + " " + ones[n % 10] + " "
        return ones[n // 100] + " Hundred " + convert_group(n % 100)

    if num == 0:
        return "Zero"
    crore = num // 10000000
    lakh = (num % 10000000) // 100000
    thousand = (num % 100000) // 1000
    remainder = num % 1000
    result = ""
    if crore > 0:
        result += convert_group(crore) + "Crore "
    if lakh > 0:
        result += convert_group(lakh) + "Lakh "
    if thousand > 0:
        result += convert_group(thousand) + "Thousand "
    if remainder > 0:
        result += convert_group(remainder)
    return result.strip()


def build_invoice_pdf(output_path, invoice_no, date_text, buyer, gstin, hsn,
                      sub_desc, qty, rate, taxable, cgst, sgst, round_off, total,
                      buyer_state="Gujarat", buyer_state_code="24", seller=None):
    seller = seller or {}
    seller_name = seller.get("name") or os.getenv("INVOICE_SELLER_NAME", "YOUR BUSINESS NAME")
    seller_line1 = seller.get("address_1") or os.getenv("INVOICE_SELLER_ADDRESS_1", "YOUR ADDRESS LINE 1")
    seller_line2 = seller.get("address_2") or os.getenv("INVOICE_SELLER_ADDRESS_2", "YOUR ADDRESS LINE 2")
    seller_line3 = seller.get("address_3") or os.getenv("INVOICE_SELLER_ADDRESS_3", "YOUR CITY - PINCODE")
    seller_gstin = seller.get("gstin") or os.getenv("INVOICE_SELLER_GSTIN", "YOUR GSTIN")
    seller_state = seller.get("state") or os.getenv("INVOICE_SELLER_STATE", "Gujarat")
    seller_state_code = seller.get("state_code") or os.getenv("INVOICE_SELLER_STATE_CODE", "24")

    pdf = FPDF(unit="mm", format="A4")
    pdf.add_page()
    pdf.set_margins(10, 10, 10)
    page_w = 190

    pdf.set_font("Arial", "B", 12)
    pdf.cell(page_w, 8, "Tax Invoice", ln=True, align="C")

    start_y = 18
    pdf.rect(10, start_y, page_w, 260)
    pdf.set_xy(10, start_y)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(95, 6, f" {seller_name}", ln=True)
    pdf.set_font("Arial", "", 9)
    pdf.cell(95, 4, f" {seller_line1}", ln=True)
    pdf.cell(95, 4, f" {seller_line2}", ln=True)
    pdf.cell(95, 4, f" {seller_line3}", ln=True)
    pdf.cell(95, 4, f" GSTIN/UIN: {seller_gstin}", ln=True)
    pdf.cell(95, 4, f" State Name: {seller_state}, Code: {seller_state_code}", ln=True)

    pdf.line(105, start_y, 105, start_y + 84)
    pdf.line(152.5, start_y, 152.5, start_y + 72)
    for y_offset in [12, 24, 36, 48, 60, 72, 84]:
        pdf.line(105, start_y + y_offset, 200, start_y + y_offset)

    pdf.set_font("Arial", "", 8)
    pdf.set_xy(105, start_y)
    pdf.cell(47.5, 4, " Invoice No.")
    pdf.set_xy(105, start_y + 4)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(47.5, 5, f" {invoice_no}")
    pdf.set_font("Arial", "", 8)
    pdf.set_xy(152.5, start_y)
    pdf.cell(47.5, 4, " Dated")
    pdf.set_xy(152.5, start_y + 4)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(47.5, 5, f" {date_text}")

    pdf.set_font("Arial", "", 8)
    for offset, left, right in [
        (12, " Delivery Note", " Mode/Terms of Payment"),
        (24, " Reference No. & Date.", " Other References"),
        (36, " Buyer's Order No.", " Dated"),
        (48, " Dispatch Doc No.", " Delivery Note Date"),
        (60, " Dispatched through", " Destination"),
    ]:
        pdf.set_xy(105, start_y + offset)
        pdf.cell(47.5, 5, left)
        pdf.set_xy(152.5, start_y + offset)
        pdf.cell(47.5, 5, right)
    pdf.set_xy(105, start_y + 72)
    pdf.cell(95, 5, " Terms of Delivery")

    pdf.line(10, start_y + 36, 105, start_y + 36)
    pdf.set_xy(10, start_y + 36)
    pdf.set_font("Arial", "", 8)
    pdf.cell(95, 5, " Buyer (Bill to)", ln=True)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(95, 5, f" {buyer}", ln=True)
    pdf.set_font("Arial", "", 9)
    pdf.cell(20, 5, " GSTIN/UIN")
    pdf.cell(75, 5, f": {gstin}", ln=True)
    pdf.cell(20, 5, " State Name")
    pdf.cell(75, 5, f": {buyer_state}, Code: {buyer_state_code}", ln=True)

    table_y = start_y + 84
    pdf.line(10, table_y, 200, table_y)
    cols = [10, 65, 20, 25, 15, 12, 15, 28]
    x_positions = [10]
    for width in cols:
        x_positions.append(x_positions[-1] + width)
    pdf.set_xy(10, table_y)
    pdf.set_font("Arial", "B", 8)
    headers = ["SI No", "Description of Goods", "HSN/SAC", "Quantity", "Rate", "per", "Disc. %", "Amount"]
    for i, header in enumerate(headers):
        pdf.set_xy(x_positions[i], table_y)
        pdf.cell(cols[i], 10, header, align="C")
    pdf.line(10, table_y + 10, 200, table_y + 10)
    for x in x_positions[1:-1]:
        pdf.line(x, table_y, x, 210)

    pdf.set_font("Arial", "", 9)
    data_y = table_y + 12
    pdf.set_xy(10, data_y)
    pdf.cell(cols[0], 5, "1", align="C")
    pdf.set_xy(x_positions[1], data_y)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(cols[1], 5, " JOB WORK INCOME")
    pdf.set_xy(x_positions[1], data_y + 5)
    pdf.set_font("Arial", "", 9)
    pdf.cell(cols[1], 5, f" {sub_desc}")
    pdf.set_xy(x_positions[2], data_y)
    pdf.cell(cols[2], 5, hsn, align="C")
    pdf.set_xy(x_positions[3], data_y)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(cols[3] - 2, 5, f"{qty:,.2f} MTR", align="R")
    pdf.set_xy(x_positions[4], data_y)
    pdf.set_font("Arial", "", 9)
    pdf.cell(cols[4] - 2, 5, f"{rate:.2f}", align="R")
    pdf.set_xy(x_positions[5], data_y)
    pdf.cell(cols[5], 5, "MTR", align="C")
    pdf.set_xy(x_positions[7], data_y)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(cols[7] - 2, 5, f"{taxable:,.2f}", align="R")

    pdf.set_font("Arial", "", 9)
    for offset, label, value in [(15, " CGST", cgst), (22, " SGST", sgst), (35, " ROUND OFF", round_off)]:
        pdf.set_xy(x_positions[1], data_y + offset)
        pdf.cell(cols[1], 5, label)
        pdf.set_xy(x_positions[7], data_y + offset)
        pdf.cell(cols[7] - 2, 5, f"{value:,.2f}", align="R")

    pdf.line(10, 203, 200, 203)
    pdf.set_font("Arial", "B", 9)
    pdf.set_xy(x_positions[1], 204)
    pdf.cell(cols[1] - 2, 5, "Total", align="R")
    pdf.set_xy(x_positions[3], 204)
    pdf.cell(cols[3] - 2, 5, f"{qty:,.2f} MTR", align="R")
    pdf.set_xy(x_positions[7], 204)
    pdf.cell(cols[7] - 2, 5, f"{total:,.2f}", align="R")
    pdf.line(10, 210, 200, 210)

    pdf.set_xy(10, 211)
    pdf.set_font("Arial", "", 8)
    pdf.cell(190, 5, " Amount Chargeable (in words)")
    pdf.set_xy(10, 216)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(190, 5, f" INR {num_to_words_inr(int(total))} Only")
    pdf.set_font("Arial", "", 8)
    pdf.set_xy(180, 216)
    pdf.cell(20, 5, "E. & O.E", align="R")
    pdf.line(10, 222, 200, 222)

    tax_y = 222
    pdf.line(45, tax_y, 45, tax_y + 22)
    pdf.line(75, tax_y, 75, tax_y + 22)
    pdf.line(115, tax_y, 115, tax_y + 22)
    pdf.line(155, tax_y, 155, tax_y + 22)
    pdf.line(10, tax_y + 8, 200, tax_y + 8)
    pdf.set_font("Arial", "", 8)
    pdf.set_xy(10, tax_y)
    pdf.cell(35, 8, " HSN/SAC", align="C")
    pdf.set_xy(45, tax_y)
    pdf.cell(30, 8, "Taxable Value", align="C")
    pdf.set_xy(75, tax_y)
    pdf.cell(40, 4, "CGST", align="C")
    pdf.set_xy(115, tax_y)
    pdf.cell(40, 4, "SGST/UTGST", align="C")
    pdf.set_xy(155, tax_y)
    pdf.cell(45, 8, "Total Tax Amount", align="C")
    pdf.line(75, tax_y + 4, 155, tax_y + 4)
    pdf.set_xy(75, tax_y + 4)
    pdf.cell(20, 4, "Rate", align="C")
    pdf.cell(20, 4, "Amount", align="C")
    pdf.line(95, tax_y + 4, 95, tax_y + 22)
    pdf.set_xy(115, tax_y + 4)
    pdf.cell(20, 4, "Rate", align="C")
    pdf.cell(20, 4, "Amount", align="C")
    pdf.line(135, tax_y + 4, 135, tax_y + 22)
    pdf.set_xy(10, tax_y + 8)
    pdf.cell(35, 7, hsn, align="C")
    pdf.set_xy(45, tax_y + 8)
    pdf.cell(30, 7, f"{taxable:,.2f}", align="R")
    pdf.set_xy(75, tax_y + 8)
    pdf.cell(20, 7, "2.50%", align="R")
    pdf.set_xy(95, tax_y + 8)
    pdf.cell(18, 7, f"{cgst:,.2f}", align="R")
    pdf.set_xy(115, tax_y + 8)
    pdf.cell(20, 7, "2.50%", align="R")
    pdf.set_xy(135, tax_y + 8)
    pdf.cell(18, 7, f"{sgst:,.2f}", align="R")
    pdf.set_xy(155, tax_y + 8)
    pdf.cell(43, 7, f"{(cgst + sgst):,.2f}", align="R")
    pdf.line(10, tax_y + 15, 200, tax_y + 15)
    pdf.set_font("Arial", "B", 8)
    pdf.set_xy(10, tax_y + 15)
    pdf.cell(35, 7, "Total", align="R")
    pdf.set_xy(45, tax_y + 15)
    pdf.cell(30, 7, f"{taxable:,.2f}", align="R")
    pdf.set_xy(95, tax_y + 15)
    pdf.cell(18, 7, f"{cgst:,.2f}", align="R")
    pdf.set_xy(135, tax_y + 15)
    pdf.cell(18, 7, f"{sgst:,.2f}", align="R")
    pdf.set_xy(155, tax_y + 15)
    pdf.cell(43, 7, f"{(cgst + sgst):,.2f}", align="R")
    pdf.line(10, tax_y + 22, 200, tax_y + 22)

    tax_total_int = int(cgst + sgst)
    tax_paise = int(round(((cgst + sgst) - tax_total_int) * 100))
    paise_str = f" and {tax_paise} paise" if tax_paise > 0 else ""
    pdf.set_xy(10, tax_y + 23)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(190, 5, f" Tax Amount (in words): INR {num_to_words_inr(tax_total_int)}{paise_str} Only")
    pdf.line(10, tax_y + 29, 200, tax_y + 29)
    pdf.set_xy(10, tax_y + 30)
    pdf.set_font("Arial", "", 8)
    pdf.cell(100, 4, " Declaration", ln=True)
    pdf.cell(100, 4, " We declare that this invoice shows the actual price of", ln=True)
    pdf.cell(100, 4, " the goods described and that all particulars are true", ln=True)
    pdf.cell(100, 4, " and correct.", ln=True)
    pdf.line(100, tax_y + 29, 100, 278)
    pdf.set_font("Arial", "B", 9)
    pdf.set_xy(100, tax_y + 30)
    pdf.cell(90, 4, f" for {seller_name}", align="R")
    pdf.set_xy(100, 270)
    pdf.cell(90, 4, " Authorised Signatory", align="R")
    pdf.set_font("Arial", "B", 8)
    pdf.set_xy(10, 270)
    pdf.cell(90, 4, " This is a Computer Generated Invoice", align="C")
    pdf.output(str(output_path))
