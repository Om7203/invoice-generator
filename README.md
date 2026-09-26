# Pure Invoice Generator

Mobile-friendly Streamlit invoice generator for in-house business use.

This public repository contains reusable code only. It intentionally does not contain customer names, GSTINs, invoices, PDFs, Excel files, or business database files. Use the placeholder customer data in `examples/` for testing, then enter the real data into the private deployed app/database.

## Features

- Gujarati and English interface
- English invoice PDFs in the existing one-page A4 format
- Editable invoice number and invoice date, including past dates
- Duplicate invoice-number protection
- Customer-specific description dropdowns and rates
- Add and save new customers
- Invoice history and Excel backup export
- Mobile PDF download
- Mobile **Share PDF on WhatsApp** button using the phone's native share menu
- Local SQLite mode for development
- Free Supabase mode for cloud storage

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Without Supabase secrets, the app uses `local_data/`, which is ignored by Git. This is only for local testing.

Set `APP_PIN` in `.streamlit/secrets.toml` before opening the app. See SETUP.md for the configuration format.

## Current validation and limitations

This is an initial implementation, not a verified production release. Python syntax has been checked; deployment and real-phone PDF sharing still need testing. Streamlit embeds the share control in an iframe, whose permissions may prevent file sharing even on a browser that supports it. The PDF download button is the fallback.

The current layout supports one line item and fixed 2.5% CGST plus 2.5% SGST. A shared PIN provides basic access control, not individual accounts or robust brute-force protection. Supabase stores PDF bytes as base64 in the database for this small-use prototype, consuming more space than binary storage. Free hosting and database availability are subject to provider limits and inactivity pauses.

## Appearance

The app supports Streamlit's Light, Dark and System appearance options. The checked-in `.streamlit/config.toml` defines matching light and dark palettes without forcing a light background. The embedded PDF sharing panel uses its own high-contrast navy surface in either mode. This requires Streamlit 1.52 or newer. After deployment, check Settings → Theme in both modes, including dropdowns, reports and PDF download controls.

## Monthly reporting

Choose Monthly report, then a month and year. The default is the current month in India. Reports use invoice date rather than creation date, so backdated invoices appear in the correct period. The screen shows total billed (including tax and rounding), meters, invoice count, taxable value, CGST, SGST, customer totals and every matching invoice. Download monthly Excel ledger exports those invoice records with their stored financial values. No payment tracking is included.

History displays 20 invoices per page. Its Excel backup includes all records, and monthly exports include all records in the selected month. Database reads are paginated to avoid the previous 100-record limit and server response caps. Reports include only invoices saved in this app, not historical desktop files that have not been imported. Download and retain periodic Excel backups yourself; exporting does not schedule automatic backups.

## Free cloud deployment

Read [SETUP.md](SETUP.md). The short version is:

1. Create a free Supabase project.
2. Run `supabase/schema.sql` in Supabase SQL Editor.
3. Create a free Streamlit Community Cloud app from this GitHub repository.
4. Add the secrets listed in `SETUP.md`.
5. Share the Streamlit URL with the family.

## Important privacy note

The GitHub repository is public for portfolio and learning purposes. Keep all real customer data, invoice PDFs, database exports, Supabase keys, and app PINs out of GitHub. They belong in Streamlit Secrets or the private Supabase database.
