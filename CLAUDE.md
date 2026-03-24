# CLAUDE.md — cb-dashboard-margenes

## Project Overview

A single-file Streamlit web application that visualizes service profit margins from uploaded Excel files. The UI is in Spanish and targets non-technical business users.

## Tech Stack

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.x | Language |
| Streamlit | 1.35.0 | Web UI framework |
| Pandas | 2.2.2 | Data processing |
| OpenPyXL | 3.1.2 | Excel file I/O |

## Repository Structure

```
cb-dashboard-margenes/
├── app.py            # Entire application (single file, ~96 lines)
├── requirements.txt  # Python dependencies
└── CLAUDE.md         # This file
```

## Running the App

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501` by default.

## Application Architecture

`app.py` is a monolithic single-file Streamlit app. Streamlit re-runs the entire script on every user interaction (reactive model).

### Data Flow

1. User uploads an `.xlsx` / `.xls` file via the file uploader
2. Pandas reads it with the `openpyxl` engine
3. All column names are normalized via `_clean()` (removes accents, lowercases, replaces special chars)
4. Columns are auto-detected by keyword matching (no fixed schema required)
5. KPI metrics are computed and displayed (total sales, total utility, average margin)
6. User can filter rows by service name
7. Filtered data is shown as a table and a bar chart
8. User can download filtered data as Excel

### Key Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `_clean(col)` | line 16 | Normalizes column names: strips accents, lowercases, replaces `%`→`porc`, `$`→`usd`, spaces→`_` |
| `_to_excel(df_)` | line 85 | Converts DataFrame to Excel bytes; decorated with `@st.cache_data` to avoid recomputation |

### Column Auto-Detection Logic

The app maps columns by keyword matching on normalized names:

| Variable | Detected when column contains |
|----------|-------------------------------|
| `col_servicio` | `"servicio"` (fallback: first column) |
| `col_venta` | `("precio"` AND `"venta")` OR exactly `"venta"` |
| `col_utilidad_abs` | `("utilidad"` AND NOT `"porc")` OR `"ganancia"` |
| `col_utilidad_pct` | `("utilidad"` AND `"porc")` OR `"margen"` |

If `col_venta`, `col_utilidad_abs`, or `col_utilidad_pct` cannot be detected, the app shows a warning with detected column names and stops (`st.stop()`).

## Code Conventions

- **Language:** Spanish for all UI strings, error messages, and variable names with business meaning
- **Naming:** `snake_case`; private/internal functions prefixed with `_`
- **Type hints:** Used on function signatures (`def _clean(col: str) -> str`)
- **Caching:** Use `@st.cache_data` for any function that transforms data and is called on every rerun
- **Error handling:** Wrap Excel reads in try/except and call `st.stop()` after showing errors — do not let exceptions propagate to the user
- **No global mutable state:** All data flows through local variables inside the `if uploaded_file:` block

## Making Changes

### Adding a New KPI Metric
1. Detect the relevant column using a `next(...)` pattern matching normalized column names
2. Add it to the validation check (`if not all([...])`)
3. Add a new `st.columns` slot and call `.metric()`

### Adding a New Chart
Place it after the existing bar chart section (line 71). Use `st.bar_chart`, `st.line_chart`, or `st.altair_chart` as appropriate. Always guard with `if not chart_df.empty`.

### Modifying Column Detection
Edit the `next(...)` expressions (lines 35–38). After any change, test with an Excel file that has both standard column names and edge-case names (with accents, mixed case, extra spaces).

## Dependencies

Install exact versions to avoid compatibility issues:

```bash
pip install -r requirements.txt
```

`xlsxwriter` is used implicitly by `_to_excel` via `engine="xlsxwriter"` — add it to `requirements.txt` if it is not already installed in the environment.

## No Tests / No CI

There are currently no automated tests or CI/CD pipelines. When adding tests, use `pytest` and mock `streamlit` components with `unittest.mock` or the `streamlit.testing` utilities introduced in Streamlit 1.18+.

## Git Branches

- `main` / `master` — stable branch
- Feature branches follow the pattern `claude/<description>-<id>`

## Deployment

The app has no Dockerfile or cloud config. For deployment:
- **Streamlit Cloud:** Push to GitHub; connect via share.streamlit.io (requires `requirements.txt` in the repo root)
- **Local/server:** `streamlit run app.py --server.port 8080`
