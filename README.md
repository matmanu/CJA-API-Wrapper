# Adobe CJA Report Runner

A lightweight Streamlit app to run **Adobe Customer Journey Analytics (CJA) Reporting API** requests interactively, preview the results as a table, and export them to CSV — without writing a new script for every report.

## Features

- OAuth **Server-to-Server** authentication against Adobe IMS (client credentials flow)
- Paste any raw CJA `POST /reports` request body and run it directly
- Automatic conversion of the JSON response into a pandas DataFrame
- Supports both **single-dimension** and **multi-dimension** reports (CJA's "multiple dimension reporting" with a `dimensions` array)
- CSV export of the resulting table
- A **debug panel** that shows the raw structure of the first response row, useful for adjusting the parser if Adobe changes the response shape

## Requirements

- Python 3.9+
- An Adobe Developer Console project with access to the **Customer Journey Analytics API**, using the **Server-to-Server (OAuth Server-to-Server)** credential type

### Python dependencies

```
streamlit
requests
pandas
```

Install with:

```bash
pip install -r requirements.txt
```

## Setup

### 1. Get your Adobe credentials

From the [Adobe Developer Console](https://developer.adobe.com/console), create (or open) a project with the CJA API added, using **OAuth Server-to-Server** authentication. You will need:

- `client_id`
- `client_secret` (sometimes labeled `secret`)
- `org_id` (the IMS Org ID)
- `scope` / `scopes` (the OAuth scopes granted to the credential)

### 2. Create a credentials JSON file

Save a JSON file locally (never commit it to the repo) with this structure:

```json
{
  "client_id": "YOUR_CLIENT_ID",
  "client_secret": "YOUR_CLIENT_SECRET",
  "org_id": "YOUR_ORG_ID@AdobeOrg",
  "scope": "YOUR_SCOPES"
}
```

Notes:
- `client_secret` can also be named `secret`.
- `scope` can also be named `scopes` (either a single string or Adobe's comma-separated scope string, depending on how your console exposes it).
- Both `client_id` and `org_id` are required.

### 3. Run the app

```bash
streamlit run API_Request_wrapper.py
```

## Usage

1. Open the app and, in the sidebar, upload your credentials JSON file.
2. In the main panel, paste (or edit) the JSON body for your `POST /reports` request — a working example for a single-dimension report is pre-filled.
3. Click **"Run report"**.
4. The app will:
   - Request an OAuth access token from Adobe IMS
   - Call `https://cja.adobe.io/reports` with your payload
   - Parse the response into a table
   - Show a **Debug** expander with the raw first row and the `columns` block from the response — open it if a dimension column looks empty or wrong
   - Let you download the table as CSV
5. Optionally check "Show full JSON response" in the sidebar to see the full raw JSON response.

### Multi-dimension reports

CJA supports up to **5 dimensions in a single request** via a `dimensions` array (instead of the single `dimension` string):

```json
"dimensions": [
  { "id": "variables/product", "dimensionColumnId": "0" },
  { "id": "variables/device_type", "dimensionColumnId": "1" }
]
```

The app detects this automatically and creates one column per dimension. Adobe does not fully document the exact per-row response shape for this case, so if a dimension column comes back empty, open the **Debug** expander after running the report, copy the raw first row, and adjust the parsing logic in `cja_response_to_df()` accordingly.

## Security notes

- **Never commit your credentials JSON file to GitHub.** Add it to `.gitignore`.
- The app never persists the uploaded credentials file to disk — it's read in memory for the session only.
- Access tokens are requested fresh on every report run and are not cached or stored.

## Suggested `.gitignore`

```
*.json
!requirements.json
.venv/
__pycache__/
.streamlit/
```
(Adjust if you want to keep some JSON files, e.g. a config template, tracked.)

## Project structure

```
.
├── API_Request_wrapper.py   # Main Streamlit app
├── requirements.txt         # Python dependencies
└── README.md                 # This file
```

## License

Released under the [MIT License](LICENSE) — free to use, modify, and distribute, provided the original copyright notice is retained.
