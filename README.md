# GridSync

**Find where neighboring electric utilities are about to build in the same place at the same time.**

GridSync pulls in planned transmission and substation projects from utility filings, puts them on one map, and flags pairs of projects that overlap in location and schedule. For any group of overlapping projects, it can also produce an AI-written coordination report covering shared corridors, schedule alignment, and ways to save money.

---

## Why it exists

Neighboring utilities, such as Dominion Energy South Carolina and Georgia Power, plan their capital projects years ahead and mostly on their own. When two utilities build near each other in the same window, the result can be:

- right-of-way cleared twice
- outage schedules that conflict
- crews, laydown yards, and heavy equipment mobilized twice
- missed chances for the interregional coordination that FERC Order 1920 now asks for

GridSync makes those overlaps visible early enough to act on.

## How it works

```
 Utility filings (PDF)                 CSV / XLSX / JSON
          │                                    │
          ▼                                    ▼
 utility-parser/main.py              POST /api/parse/upload
 Gemini extracts structured           → POST /api/projects
 project records
          │                                    │
          └──────────────┬─────────────────────┘
                         ▼
               Supabase  `projects` table
                         │
                         ▼
               Flask API  (app.py, backend/)
               • proximity + timeline overlap analysis
               • Gemini coordination reports
                         │
                         ▼
               React + Leaflet map  (frontend/)
```

1. **Ingest.** PDF capital plans go to Google Gemini, which returns structured JSON for each project: name, utility, state, a regional centroid lat/lng, in-service date, estimated cost, and scope. The records are normalized (dates to `YYYY-MM-DD`, coordinates rounded to regional precision) and upserted into Supabase.
2. **Analyze.** The backend compares every pair of projects with the haversine distance, sorts each pair into a proximity tier, and checks whether their build windows overlap.
3. **Visualize.** The React frontend shows every project on a Leaflet map. You can filter by utility, year, state, or title, and lines connect projects that overlap.
4. **Report.** Select two or more projects and Gemini writes a structured report covering spatial and corridor synergy, schedule alignment, and strategic recommendations.

### Proximity tiers

| Tier | Distance | What it suggests |
| :--- | :--- | :--- |
| `under_1.6km` | < 1 mi | Share land and right-of-way; coordinate crossings and outages |
| `under_8km` | < 5 mi | Share laydown yards, equipment deliveries, and contractor pools |
| `under_40km` | < 25 mi | Coordinate labor and crew staging across the region |

Pairs are also marked as **cross-utility** when the two projects belong to different companies. Those pairs are the real coordination opportunities.

---

## Tech stack

| Layer | Technology |
| :--- | :--- |
| **Frontend** | React 19, Vite, Leaflet + React-Leaflet, oxlint |
| **Backend API** | Python, Flask, Flask-CORS, Pydantic v2, pandas, openpyxl |
| **Database** | Supabase (hosted PostgreSQL) via `supabase-py` |
| **AI / LLM** | Google Gemini via the `google-genai` SDK, with Pydantic response schemas for structured JSON output |
| **Data ingestion** | Python script using the Gemini Files API for PDF extraction |
| **Config** | `python-dotenv` (`.env` at the repo root) |

---

## Project structure

```
Universal-Electric-Hub/
├── app.py                     # Flask entry point; also serves the built frontend
├── requirements.txt           # Python dependencies
├── backend/
│   ├── config.py              # Loads .env and holds app settings
│   ├── models/project.py      # Normalized Project model and date parsing
│   ├── routes/
│   │   ├── health.py          # GET  /api/health
│   │   ├── projects.py        # GET/POST /api/projects
│   │   ├── parse.py           # POST /api/parse/upload
│   │   └── analysis.py        # /api/analysis/overlaps, /api/analysis/report
│   └── services/
│       ├── parser.py          # CSV/XLSX/JSON → Project, with column aliases
│       ├── proximity.py       # Haversine distance, tiers, timeline overlap
│       ├── ai_report.py       # Gemini coordination report
│       ├── project_repo.py    # Supabase reads and writes
│       └── supabase_client.py
├── utility-parser/
│   ├── main.py                # PDF → Gemini → Supabase ingestion pipeline
│   ├── ai_cross_reference_popup.py
│   └── api.py                 # Earlier FastAPI prototype (not used by the frontend)
└── frontend/
    ├── vite.config.js         # Proxies /api to Flask on :5000 during dev
    └── src/
        ├── App.jsx            # Map, filters, project list, report sidebar
        └── api.js             # API client
```

---

## Getting started

### Prerequisites

- Python 3.11+
- Node.js 20+
- A [Supabase](https://supabase.com) project
- A Google Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

### 1. Configure environment variables

Create a `.env` file in the **repo root**. It is gitignored.

```bash
SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_KEY=<your-supabase-key>
GEMINI_API_KEY=<your-gemini-api-key>

# Optional
GEMINI_MODEL=gemini-3.8-flash   # model used for coordination reports
CORS_ORIGINS=*
```

### 2. Create the Supabase table

The app reads and writes one `projects` table:

```sql
create table projects (
  id               bigint generated always as identity primary key,
  created_at       timestamptz default now(),
  project_name     text not null,
  utility_company  text,
  state            text,
  latitude         double precision,
  longitude        double precision,
  in_service_date  text,
  price            double precision,
  project_scope    text
);
```

### 3. Install and run the backend

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate
# Windows (PowerShell)
venv\Scripts\Activate.ps1

pip install -r requirements.txt
python app.py
```

The API runs at `http://localhost:5000`. To check that it's up, open `http://localhost:5000/api/health`.

### 4. Run the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite forwards every `/api` request to Flask.

### Production build (optional)

```bash
cd frontend && npm run build && cd ..
python app.py
```

Flask serves the built app from `frontend/dist`, so the whole app runs at `http://localhost:5000` from one process.

### Deploy to Render

The included `render.yaml` installs the backend dependencies, builds the React
app in `frontend/dist`, and starts Gunicorn from the repository root. Configure
`SUPABASE_URL`, `SUPABASE_KEY`, and `GEMINI_API_KEY` as Render environment
variables. `frontend/dist` is generated during deployment and should not be
committed.

---

## Loading data

### From utility PDF filings

1. Put the PDF filings, such as a utility's transmission plan or IRP appendix, in `utility-parser/`.
2. Run:

   ```bash
   python utility-parser/main.py
   ```

Gemini extracts each project and writes it to Supabase. Each processed PDF moves to `utility-parser/processed/`. If you run the script again, it re-scans those files in update mode, so you don't get duplicate rows.

> Coordinates are **regional centroids** (corridor midpoints or county centroids), not exact site locations. They're meant for finding overlaps at the tier level, not for engineering-grade routing.

### From a spreadsheet

Upload a CSV, XLSX, or JSON file to `POST /api/parse/upload` to validate it. Then send the returned `projects` list to `POST /api/projects` to save it. Common column spellings are mapped automatically, for example `latitude`/`lat`, `longitude`/`lon`/`lng`, `project_name`/`name`, and `utility_company`/`company`/`owner`.

---

## API reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/projects?state=SC&utility=dominion` | List projects; both filters are optional |
| `POST` | `/api/projects` | Save projects. Body: `{"projects": [...]}` |
| `POST` | `/api/parse/upload` | Parse an uploaded file (form field `file`) into projects without saving |
| `GET` | `/api/analysis/overlaps?max_km=40&cross_utility_only=true` | Find overlapping pairs across all stored projects |
| `POST` | `/api/analysis/overlaps` | Find overlapping pairs in projects sent in the body |
| `POST` | `/api/analysis/report` | Gemini coordination report. Body: `{"project_ids": [1, 2]}` |

Errors come back as `{"error": "...", "message": "..."}` with the matching HTTP status code.

---

## Roadmap

- Move proximity checks into the database with PostGIS `ST_DWithin`
- Use real line geometries (LineStrings) instead of point centroids for route-crossing detection
- Add a shared-trench and right-of-way cost-savings calculator
- Add a timeline slider to replay construction windows year by year
