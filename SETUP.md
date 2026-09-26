# Setup guide

This guide is written for the owner of the app. No paid plan, domain, Android package, or WhatsApp Business API is required for the basic family workflow.

## 1. GitHub

The source repository is:

`https://github.com/Om7203/invoice-generator`

The repository may remain public because this project contains code and placeholders only. Never commit real invoices, customer lists, GSTINs, PDFs, Excel files, `.streamlit/secrets.toml`, or database files.

## 2. Supabase database

1. Create a free account at [supabase.com](https://supabase.com).
2. Create a new project.
3. Open **SQL Editor**.
4. Copy and run the contents of `supabase/schema.sql`.
5. In **Project Settings → API**, copy the **Project URL** and the **service_role key**.

Keep the service-role key private. It must only be entered into Streamlit Secrets, never into GitHub or WhatsApp.

## 3. Streamlit Community Cloud

1. Open [share.streamlit.io](https://share.streamlit.io).
2. Sign in with the GitHub account that owns this repository.
3. Choose **Create app**.
4. Select repository `Om7203/invoice-generator`.
5. Set the main file to `streamlit_app.py`.
6. Deploy.

In the app's **Settings → Secrets**, add the following TOML. Replace every placeholder with your own value:

```toml
APP_PIN = "choose-a-family-pin"
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_SERVICE_KEY = "your-private-service-role-key"

INVOICE_SELLER_NAME = "YOUR BUSINESS NAME"
INVOICE_SELLER_ADDRESS_1 = "YOUR ADDRESS LINE 1"
INVOICE_SELLER_ADDRESS_2 = "YOUR ADDRESS LINE 2"
INVOICE_SELLER_ADDRESS_3 = "YOUR CITY - PINCODE"
INVOICE_SELLER_GSTIN = "YOUR GSTIN"
INVOICE_SELLER_STATE = "Gujarat"
INVOICE_SELLER_STATE_CODE = "24"
```

After saving Secrets, reboot the app. The app will use Supabase automatically. If Supabase is not configured, it falls back to local SQLite for development.

## 4. Add the real customers

Use **Add new customer** inside the app. For descriptions, enter one per line:

```text
ROTO - 60 | 4.05
ROTO - 60 BLACK | 4.10
```

The customer list is stored in Supabase and appears on every device.

## 5. Give it to your father

1. Send him the Streamlit app link on WhatsApp.
2. He opens it in Chrome on Android.
3. He enters the family PIN.
4. He creates the invoice.
5. He taps **Share PDF on WhatsApp** and chooses the recipient.

The direct file share works best in Android Chrome over HTTPS. If the phone does not support file sharing, the app provides a download fallback; he can then attach the downloaded PDF in WhatsApp.

## Troubleshooting

- **App wakes slowly:** Streamlit Community Cloud sleeps inactive apps. Wait for it to wake.
- **Customer table error:** run `supabase/schema.sql` again and confirm the Project URL and service-role key.
- **PDF has placeholders:** update the `INVOICE_SELLER_*` secrets and reboot the app.
- **WhatsApp opens without a PDF:** use the download fallback. The browser may not support file sharing in that device/browser.
