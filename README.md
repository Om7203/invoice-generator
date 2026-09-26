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

## Free cloud deployment

Read [SETUP.md](SETUP.md). The short version is:

1. Create a free Supabase project.
2. Run `supabase/schema.sql` in Supabase SQL Editor.
3. Create a free Streamlit Community Cloud app from this GitHub repository.
4. Add the secrets listed in `SETUP.md`.
5. Share the Streamlit URL with the family.

## Important privacy note

The GitHub repository is public for portfolio and learning purposes. Keep all real customer data, invoice PDFs, database exports, Supabase keys, and app PINs out of GitHub. They belong in Streamlit Secrets or the private Supabase database.
