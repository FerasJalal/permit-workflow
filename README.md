# Permit Workflow API

Automated permit lifecycle system built with FastAPI. Handles the full flow from permit request through e-signature to archival.

```
Request → Template Fill → Email → Upload → Validate → PDF → Sign → Archive → Notify
```

## Architecture

```
POST /permits
  │
  ├─ Create permit records in DB (one per permit type)
  ├─ Fill matching .xlsx template (openpyxl)
  └─ Email requester with Excel + upload link (Microsoft Graph)
        │
        ▼
POST /permits/{id}/upload
  │
  ├─ Validate required cells are filled
  │   └─ If invalid → return errors, allow re-upload
  ├─ Convert Excel to PDF (LibreOffice headless)
  ├─ Upload to Adobe Sign as transient document
  └─ Create agreement: Owner → Coordinator → Approver
        │
        ▼
POST /webhooks/adobe-sign  (signing complete)
  │
  ├─ Download signed PDF
  ├─ Upload to SharePoint
  ├─ Update DB with SharePoint URL
  └─ Email signed permit to all parties
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure credentials
cp .env.example .env
# Edit .env with your API keys (see Configuration below)

# Generate sample templates
python create_sample_template.py

# Start the server
uvicorn main:app --reload

# Open API docs
# http://localhost:8000/docs
```

### Run the test suite

The end-to-end test mocks all external services so it runs anywhere:

```bash
python test_workflow.py
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/permits` | Create a permit request (triggers template fill + email) |
| `GET` | `/permits` | List all permit requests |
| `GET` | `/permits/{request_id}` | Get a permit request with all its permits |
| `GET` | `/permits/{request_id}/permits/{permit_id}` | Get a single permit |
| `POST` | `/permits/{permit_id}/upload` | Upload completed Excel (validates, converts, sends for signing) |
| `GET` | `/webhooks/adobe-sign` | Adobe Sign webhook verification |
| `POST` | `/webhooks/adobe-sign` | Receives signing-complete events |
| `GET` | `/health` | Health check |

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

## Configuration

All credentials go in `.env` (copy from `.env.example`).

### Microsoft Graph (Email + SharePoint)

Requires an Azure AD App Registration with `Mail.Send` and `Sites.ReadWrite.All` (Application) permissions.

| Variable | Source |
|----------|--------|
| `GRAPH_TENANT_ID` | Azure Portal > Azure AD > Overview > Tenant ID |
| `GRAPH_CLIENT_ID` | Azure Portal > App Registrations > Your App > Application (client) ID |
| `GRAPH_CLIENT_SECRET` | Azure Portal > App Registrations > Your App > Certificates & secrets |
| `GRAPH_SENDER_EMAIL` | The mailbox that sends permit emails (e.g. `permits@yourorg.com`) |

### Adobe Acrobat Sign

1. Go to [Adobe Acrobat Sign](https://secure.adobesign.com) > Account > Adobe Sign API > API Applications
2. Create an application and generate an OAuth Access Token with scopes: `agreement_write`, `agreement_read`, `webhook_write`, `widget_write`

| Variable | Source |
|----------|--------|
| `ADOBE_SIGN_BASE_URL` | Data center URL. NA1: `https://api.na1.adobesign.com/api/rest/v6` |
| `ADOBE_SIGN_ACCESS_TOKEN` | The OAuth token generated above |
| `ADOBE_SIGN_WEBHOOK_URL` | Public URL for webhook events (e.g. `https://your-domain.com/webhooks/adobe-sign`) |

> For local development, use [ngrok](https://ngrok.com): `ngrok http 8000`, then set `ADOBE_SIGN_WEBHOOK_URL` to the ngrok HTTPS URL.

### SharePoint

| Variable | Source |
|----------|--------|
| `SHAREPOINT_SITE_ID` | Graph Explorer: `GET /v1.0/sites/{hostname}:/{site-path}` > `id` field |
| `SHAREPOINT_DRIVE_ID` | Graph Explorer: `GET /v1.0/sites/{site-id}/drives` > document library `id` |
| `SHAREPOINT_FOLDER_PATH` | Folder path for signed PDFs (e.g. `/Permits/Signed`) |

### App Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_BASE_URL` | `http://localhost:8000` | Base URL for upload links in emails |
| `TEMPLATES_DIR` | `templates` | Directory containing Excel templates |
| `LIBREOFFICE_PATH` | `soffice` | Path to LibreOffice binary |

## Excel Templates

Templates live in `templates/` and are matched by filename to the `permit_type` in the request.

```
templates/
├── hot_work.xlsx
├── confined_space.xlsx
├── excavation.xlsx
├── electrical.xlsx
└── general.xlsx
```

### Auto-filled cells

The system pre-fills these cells before emailing the template:

| Cell | Value |
|------|-------|
| B3 | Requester Name |
| B4 | Requester Email |
| B5 | Project Name |
| B6 | Project Location |
| B7 | Permit Type |

Edit `FIELD_MAPPING` in `app/services/template_filler.py` to change these.

### Validated cells

On upload, these cells must not be empty:

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

Edit `REQUIRED_CELLS` in `app/services/validator.py` to change these.

### Adding a new permit type

1. Create your Excel template with the form layout
2. Save it as `templates/{type_name}.xlsx`
3. Use `"permit_type": "{type_name}"` in API requests

## Permit Status Lifecycle

```
draft → template_sent → uploaded → [validation_failed] → pdf_generated → sent_for_signing → signed → completed
```

All status transitions and file paths are tracked in the `permits` table. The final signed PDF is stored in SharePoint with the URL saved in `permits.sharepoint_url`.

## Project Structure

```
├── main.py                        # FastAPI app entry point
├── requirements.txt
├── .env.example                   # Config template
├── create_sample_template.py      # Generates sample Excel templates
├── test_workflow.py               # End-to-end test (mocked services)
├── templates/                     # Excel permit templates
├── app/
│   ├── config.py                  # Settings from .env
│   ├── database.py                # SQLite + async SQLAlchemy
│   ├── models.py                  # PermitRequest, Permit models
│   ├── schemas.py                 # Pydantic request/response schemas
│   ├── routers/
│   │   ├── permits.py             # CRUD + upload endpoints
│   │   └── webhooks.py            # Adobe Sign webhook handler
│   └── services/
│       ├── template_filler.py     # openpyxl template filling
│       ├── validator.py           # Required-cell validation
│       ├── pdf_converter.py       # LibreOffice headless conversion
│       ├── graph_mail.py          # Microsoft Graph email
│       ├── adobe_sign.py          # Acrobat Sign API
│       ├── sharepoint.py          # SharePoint upload via Graph
│       └── workflow.py            # Orchestrates the full flow
├── uploads/                       # Uploaded Excel files (gitignored)
└── generated/                     # Generated PDFs (gitignored)
```

## Prerequisites

- Python 3.10+
- [LibreOffice](https://www.libreoffice.org/) (for Excel-to-PDF conversion)
- Azure AD App Registration (for Microsoft Graph)
- Adobe Acrobat Sign account with API access
- A publicly accessible URL for webhooks (or ngrok for local dev)
