# Permit Workflow — Setup Guide

## 1. Credentials & API Configuration

All credentials go in a single `.env` file at the project root.  
Copy the template and fill in your values:

```bash
cp .env.example .env
```

### Microsoft Graph (Email + SharePoint)

You need an **Azure AD App Registration** with the following permissions:
- `Mail.Send` (Application)
- `Sites.ReadWrite.All` (Application)

| Variable | Where to find it |
|----------|-----------------|
| `GRAPH_TENANT_ID` | Azure Portal → Azure Active Directory → Overview → Tenant ID |
| `GRAPH_CLIENT_ID` | Azure Portal → App Registrations → Your App → Application (client) ID |
| `GRAPH_CLIENT_SECRET` | Azure Portal → App Registrations → Your App → Certificates & secrets → New client secret |
| `GRAPH_SENDER_EMAIL` | The mailbox that will send permit emails (e.g. `permits@yourorg.com`) |

### Adobe Acrobat Sign

You need an **Adobe Sign API application**:

1. Go to [Adobe Acrobat Sign](https://secure.adobesign.com) → Account → Adobe Sign API → API Applications
2. Create a new application (or use an existing one)
3. Generate an **OAuth Access Token** with scopes:
   - `agreement_write`
   - `agreement_read`
   - `webhook_write`
   - `widget_write`

| Variable | Where to find it |
|----------|-----------------|
| `ADOBE_SIGN_BASE_URL` | Depends on your data center. NA1: `https://api.na1.adobesign.com/api/rest/v6`, EU1: `https://api.eu1.adobesign.com/api/rest/v6` |
| `ADOBE_SIGN_ACCESS_TOKEN` | The OAuth token you generated above |
| `ADOBE_SIGN_WEBHOOK_URL` | Your public URL where Adobe Sign sends events: `https://your-domain.com/webhooks/adobe-sign` |

> **Important:** The webhook URL must be publicly accessible. For local development, use a tunnel like [ngrok](https://ngrok.com): `ngrok http 8000`, then use the `https://xxxx.ngrok.io/webhooks/adobe-sign` URL.

### SharePoint Storage

| Variable | Where to find it |
|----------|-----------------|
| `SHAREPOINT_SITE_ID` | Graph Explorer: `GET https://graph.microsoft.com/v1.0/sites/{hostname}:/{site-path}` → copy the `id` field |
| `SHAREPOINT_DRIVE_ID` | Graph Explorer: `GET https://graph.microsoft.com/v1.0/sites/{site-id}/drives` → pick the document library's `id` |
| `SHAREPOINT_FOLDER_PATH` | The folder path inside that drive where signed PDFs are saved (e.g. `/Permits/Signed`) — create it in SharePoint first |

---

## 2. Excel Templates (The "Surveys")

Templates are the Excel files that get emailed to requesters to fill in. They live in the `templates/` folder.

### Where to put them

```
templates/
├── hot_work.xlsx
├── confined_space.xlsx
├── excavation.xlsx
├── electrical.xlsx
└── general.xlsx          ← add as many as you need
```

**The filename IS the permit type.** When a request comes in with `"permit_type": "hot_work"`, the system looks for `templates/hot_work.xlsx`.

### How to create a new template

1. Create an Excel file with your permit form layout
2. The system pre-fills these cells automatically:
   - `B3` → Requester Name
   - `B4` → Requester Email
   - `B5` → Project Name
   - `B6` → Project Location
   - `B7` → Permit Type
3. Add any additional fields the requester needs to fill in
4. Save it as `templates/{permit_type_name}.xlsx`

To change which cells get pre-filled, edit `FIELD_MAPPING` in `app/services/template_filler.py`.

### What gets validated

When the requester uploads the completed Excel, the validator checks these cells are not empty:

| Cell | Field |
|------|-------|
| B3 | Requester Name |
| B4 | Requester Email |
| B5 | Project Name |
| B6 | Project Location |
| B7 | Permit Type |
| B10 | Start Date |
| B11 | End Date |
| B12 | Description of Work |

To change required fields, edit `REQUIRED_CELLS` in `app/services/validator.py`.

---

## 3. How Responses Are Collected

### The flow

```
You submit a permit request via POST /permits
       ↓
System fills the matching Excel template with project info
       ↓
System emails the requester the Excel + an upload link
   (link: https://your-domain.com/permits/{permit_id}/upload)
       ↓
Requester fills in the Excel and uploads it via that link
       ↓
System validates required cells are filled
   ├── If invalid → returns errors, requester can re-upload
   └── If valid  → continues to PDF conversion & signing
```

### The upload link

When the email is sent, it contains a link like:

```
https://your-domain.com/permits/42/upload
```

This points to the `POST /permits/{permit_id}/upload` endpoint. The requester uploads their completed `.xlsx` file to this endpoint.

> **Note:** This is an API endpoint. If you want a user-friendly upload page, you'll need a simple frontend that calls this endpoint — or integrate with a file-sharing tool.

### Re-upload on validation failure

If the validator finds empty required cells, the API returns:

```json
{
  "valid": false,
  "errors": [
    "Required field 'Start Date' (cell B10) is empty",
    "Required field 'Description of Work' (cell B12) is empty"
  ]
}
```

The permit status is set to `validation_failed`, and the requester can upload again. The system only proceeds to PDF conversion and signing once all required fields pass.

---

## 4. How Responses Are Automatically Stored

Every step is tracked in the **SQLite database** (`permits.db`), and final signed documents go to **SharePoint**.

### Database storage

| What | Where | When |
|------|-------|------|
| Permit request details | `permit_requests` table | On form submission |
| Each permit's status & files | `permits` table | Updated at every step |
| Uploaded Excel path | `permits.uploaded_file` | On upload |
| Generated PDF path | `permits.pdf_file` | After PDF conversion |
| Adobe Sign agreement ID | `permits.adobe_agreement_id` | After sending for signing |
| Signed PDF path | `permits.signed_pdf_file` | After signing completes |
| SharePoint URL | `permits.sharepoint_url` | After SharePoint upload |

### SharePoint storage

Once all signers complete signing:
1. The webhook fires → system downloads the signed PDF from Adobe Sign
2. Saves it locally in `generated/signed_{permit_id}.pdf`
3. Uploads it to SharePoint at `{SHAREPOINT_FOLDER_PATH}/{project_name}_{permit_type}_signed.pdf`
4. Stores the SharePoint URL in the database
5. Emails the signed PDF to all parties (requester, owner, coordinator, approver)

### Permit status lifecycle

```
draft → template_sent → uploaded → [validation_failed] → pdf_generated → sent_for_signing → signed → completed
```

You can check any permit's status at any time:

```bash
GET /permits/{request_id}
```

---

## 5. Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure credentials
cp .env.example .env
# Edit .env with your values

# 3. Generate sample templates (or add your own to templates/)
python create_sample_template.py

# 4. Run the server
uvicorn main:app --reload

# 5. Open the API docs
# http://localhost:8000/docs
```

### Example: Create a permit request

```bash
curl -X POST http://localhost:8000/permits \
  -H "Content-Type: application/json" \
  -d '{
    "requester_name": "Ahmad Hassan",
    "requester_email": "ahmad@example.com",
    "project_name": "Building A Renovation",
    "project_location": "Downtown Amman",
    "permit_types": [
      {
        "permit_type": "hot_work",
        "owner_email": "owner@example.com",
        "coordinator_email": "coordinator@example.com",
        "approver_email": "approver@example.com"
      }
    ]
  }'
```

This triggers the entire workflow automatically.
