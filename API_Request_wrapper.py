import json
import requests
import pandas as pd
import streamlit as st


st.set_page_config(page_title="CJA Report Runner", layout="wide")
st.title("Adobe CJA Report Runner")


# ==============================
# HELPERS
# ==============================
def load_config_from_uploaded_file(uploaded_file) -> dict:
    """
    Legge il file JSON caricato da Streamlit e restituisce il dict config.
    Supporta sia 'scope' che 'scopes'.
    """
    try:
        content = uploaded_file.read().decode("utf-8")
        config = json.loads(content)
    except Exception as e:
        raise ValueError(f"Impossibile leggere il file JSON credenziali: {e}")

    required_keys = ["client_id", "org_id"]
    for key in required_keys:
        if key not in config:
            raise ValueError(f"Chiave mancante nel file credenziali: '{key}'")

    if "client_secret" not in config and "secret" not in config:
        raise ValueError("Nel file credenziali manca 'client_secret' oppure 'secret'")

    if "scope" not in config and "scopes" not in config:
        raise ValueError("Nel file credenziali manca 'scope' oppure 'scopes'")

    return config


def get_access_token(client_id: str, client_secret: str, scope: str) -> str:
    """
    Recupera il token OAuth Server-to-Server Adobe.
    """
    url = "https://ims-na1.adobelogin.com/ims/token/v3"

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
        "scope": scope
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(url, data=payload, headers=headers, timeout=60)

    try:
        response.raise_for_status()
    except requests.HTTPError:
        raise Exception(
            f"Errore nel recupero token: {response.status_code} - {response.text}"
        )

    data = response.json()
    return data["access_token"]


def run_cja_report(access_token: str, client_id: str, org_id: str, report_payload: dict) -> dict:
    """
    Esegue la POST del report CJA.
    """
    url = "https://cja.adobe.io/reports"

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
        "x-api-key": client_id,
        "x-gw-ims-org-id": org_id,
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json=report_payload, timeout=120)

    try:
        response.raise_for_status()
    except requests.HTTPError:
        raise Exception(
            f"Errore nella report request: {response.status_code} - {response.text}"
        )

    return response.json()


def _short_name(dim_id: str) -> str:
    """Riduce un id tipo 'variables/xxx.yyy.Product_Id' all'ultimo segmento leggibile."""
    if not isinstance(dim_id, str):
        return str(dim_id)
    return dim_id.split("/")[-1].split(".")[-1]


def cja_response_to_df(response_json: dict, report_payload: dict | None = None) -> pd.DataFrame:
    """
    Converte una response CJA /reports in DataFrame.
    Gestisce sia il caso classico a 1 dimensione ("columns.dimension", singolare)
    sia il caso "multiple dimension reporting" introdotto da Adobe
    ("columns.dimensions", plurale, con dimensionColumnId).

    NB: la struttura esatta di ogni riga nel caso multi-dimensione non è
    documentata pubblicamente da Adobe in modo completo: qui si prova prima
    la forma più probabile (un valore per dimensione, stesso ordine di
    columns.dimensions) e si ricade su alternative note se la prima non
    combacia con le chiavi presenti nella riga.
    """
    rows = response_json.get("rows", [])
    columns = response_json.get("columns", {})

    # --- Nomi dimensione/i ---
    dims_multi = columns.get("dimensions") if isinstance(columns, dict) else None
    if dims_multi:
        dim_names = [_short_name(d.get("id", f"dim_{i}")) for i, d in enumerate(dims_multi)]
    else:
        single_dim = columns.get("dimension", {}) if isinstance(columns, dict) else {}
        dim_names = [_short_name(single_dim.get("id", "dimension"))]

    # --- Nomi metriche: se disponibile, usa gli id reali dal payload della request
    # (molto più leggibili di "metric_0", "metric_1", ...) altrimenti fallback sui columnIds
    metric_names = None
    if report_payload:
        metrics = report_payload.get("metricContainer", {}).get("metrics", [])
        if metrics:
            metric_names = [_short_name(m.get("id", f"metric_{i}")) for i, m in enumerate(metrics)]
    if not metric_names:
        metric_names = columns.get("columnIds", []) if isinstance(columns, dict) else []

    data = []
    n_dims = len(dim_names)

    for row in rows:
        row_dict = {}

        if n_dims == 1:
            # Caso classico: un solo valore dimensione
            row_dict[dim_names[0]] = row.get("value")
        else:
            # Caso multi-dimensione: prova diverse chiavi possibili, in ordine di probabilità
            dim_values = None
            if isinstance(row.get("value"), list):
                dim_values = row["value"]
            elif isinstance(row.get("values"), list):
                dim_values = row["values"]
            elif isinstance(row.get("value"), str):
                # Fallback: valore singolo concatenato -> non separabile con certezza,
                # lo mettiamo intero nella prima colonna dimensione e lasciamo le altre vuote
                dim_values = [row["value"]] + [None] * (n_dims - 1)

            if dim_values is None:
                dim_values = [None] * n_dims

            for i, name in enumerate(dim_names):
                row_dict[name] = dim_values[i] if i < len(dim_values) else None

        values = row.get("data", [])
        for i, value in enumerate(values):
            col_name = metric_names[i] if i < len(metric_names) else f"metric_{i}"
            row_dict[col_name] = value

        data.append(row_dict)

    df = pd.DataFrame(data)

    if not df.empty:
        cleaned_columns = []
        for col in df.columns:
            if isinstance(col, str) and "/" in col:
                cleaned_columns.append(col.split("/")[-1])
            else:
                cleaned_columns.append(col)
        df.columns = cleaned_columns

        for col in df.columns[n_dims:]:
            df[col] = pd.to_numeric(df[col], errors="ignore")

    return df


# ==============================
# DEFAULT JSON EXAMPLE
# ==============================
default_report_json = {
    "rsid": "dv_xxxxxxxxxxxxxxxxx",
    "globalFilters": [
        {
            "type": "dateRange",
            "dateRange": "2026-03-01T00:00:00.000/2026-03-23T23:59:59.999"
        }
    ],
    "metricContainer": {
        "metrics": [
            {
                "columnId": "0",
                "id": "metrics/orders"
            },
            {
                "columnId": "1",
                "id": "metrics/revenue"
            }
        ]
    },
    "dimension": "variables/product",
    "settings": {
        "limit": 10,
        "page": 0
    }
}


# ==============================
# SIDEBAR
# ==============================
with st.sidebar:
    st.header("Configurazione")
    uploaded_credentials = st.file_uploader(
        "Carica file credenziali JSON",
        type=["json"]
    )

    show_raw_response = st.checkbox("Mostra risposta JSON completa", value=True)


# ==============================
# MAIN INPUT
# ==============================
st.subheader("Report request JSON")
report_json_text = st.text_area(
    "Incolla qui il JSON della report request",
    value=json.dumps(default_report_json, indent=2),
    height=350,
    placeholder='{"rsid":"dv_...","metricContainer":{...}}'
)

run_button = st.button("Esegui report", type="primary")


# ==============================
# EXECUTION
# ==============================
if run_button:
    if uploaded_credentials is None:
        st.error("Carica prima il file JSON con le credenziali.")
        st.stop()

    try:
        config = load_config_from_uploaded_file(uploaded_credentials)

        client_id = config["client_id"]
        client_secret = config.get("client_secret", config.get("secret"))
        org_id = config["org_id"]
        scope = config.get("scope", config.get("scopes"))

        report_payload = json.loads(report_json_text)

    except json.JSONDecodeError as e:
        st.error(f"Il JSON della report request non è valido: {e}")
        st.stop()
    except Exception as e:
        st.error(str(e))
        st.stop()

    with st.spinner("Recupero token e lancio report..."):
        try:
            token = get_access_token(client_id, client_secret, scope)
            result = run_cja_report(token, client_id, org_id, report_payload)
            df = cja_response_to_df(result, report_payload)

            st.success("Report eseguito con successo.")

            if result.get("rows"):
                with st.expander("Debug: struttura raw della prima riga (utile se le dimensioni non tornano corrette)"):
                    st.json(result["rows"][0])
                    st.json(result.get("columns", {}))

            st.subheader("Output tabellare")
            if df.empty:
                st.warning("La risposta è valida ma il DataFrame risulta vuoto.")
            else:
                st.dataframe(df, use_container_width=True)

                csv_data = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="Scarica CSV",
                    data=csv_data,
                    file_name="cja_report_output.csv",
                    mime="text/csv"
                )

            if show_raw_response:
                st.subheader("Risposta JSON completa")
                st.json(result)

        except Exception as e:
            st.error(str(e))