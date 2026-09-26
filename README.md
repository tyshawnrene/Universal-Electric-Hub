# GridSync FL: Interregional Utility Infrastructure Coordination Engine
**FERC Order 1920 Compliance & Capital Optimization Prototype**

---

## 🚀 Project Vision
GridSync FL is an intelligent geospatial coordination engine built to solve a multi-million-dollar industry problem: neighboring electric utilities (such as Florida Power & Light, Duke Energy Florida, and regional municipal utilities) plan capital infrastructure projects years in advance in total isolation. This historical isolation leads to redundant road digging, delayed grid reliability, and regulatory waste. 

GridSync FL ingests unstructured utility capital expenditure (CapEx) plans, standardizes them using Google AI Studio (Gemini), stores them in a spatial database (Supabase + PostGIS), and renders an interactive geospatial interface that flags overlapping construction zones, calculates shared trench savings, and generates audit-ready compliance reports for FERC Order 1920.

---

## 👥 Team Roles & Battle Station Layout

To maximize our 36-hour sprint with a diverse technical lineup, responsibilities are strictly compartmentalized:

### 1. Project Manager & Environment Lead (You)
* **Focus:** Git workflow management, environment variables, Supabase provisioning, and overall timeline tracking.
* **Responsibilities:** Oversee cross-team integration, manage merge conflicts, maintain strict adherence to the 36-hour execution schedule, and lead the final pitch deck narrative.

### 2. Backend & Database Lead (Python / Flask / SQL)
* **Focus:** API routing, database schema, spatial/temporal cross-referencing logic, and LLM orchestration.
* **Responsibilities:** Build the Flask backend, configure PostGIS spatial queries (`ST_DWithin` and temporal overlap checks), and write the Python pipeline leveraging the Google AI Studio Gemini API to extract structured JSON from raw utility filings.

### 3. Frontend Lead (HTML / CSS / JS / UI-UX)
* **Focus:** User interface, vector mapping, and interactive dashboard components.
* **Responsibilities:** Build the responsive web frontend utilizing Leaflet.js or Mapbox GL, implement the time-slider geospatial playback scrubber, and construct the visual layout for the Shared Trench Dollar Calculator.

### 4. IT Data & QA Lead (Cloud-Based Operations / Data Ingestion)
* **Focus:** Data acquisition, manual fallback preparation, and system validation.
* **Responsibilities:** Operating entirely out of browser-based cloud environments (such as GitHub Codespaces or Google IDX) to bypass local dependency hurdles. Tasked with scraping, cleaning, and formatting initial FPL and municipal CSV/PDF datasets, ensuring zero downtime for data feeds.

---

## 🏗️ Technical Architecture

* **Ingestion Layer:** Python scripts parsing raw utility PDFs and text plans via **Google AI Studio API (Gemini)** into strict JSON schemas.
* **Database & Spatial Engine:** **Supabase** hosted PostgreSQL with the **PostGIS** extension enabled for lightning-fast geospatial indexing and querying.
* **API Layer:** Lightweight **Flask** REST API handling spatial queries, CRUD operations, and ROI calculations.
* **Frontend UI:** Modern, lightweight HTML5/CSS3/TypeScript dashboard integrated with **Leaflet.js** for vector tile rendering and custom timeline scrubbing.

---

## ⏱️ Step-by-Step 36-Hour Execution Phases

### Phase 1: Foundation & Data Lock (Hours 0 – 6)
* **Action Items:**
  * Spin up Supabase instance, enable PostGIS, and execute schema migrations for `utilities`, `projects`, and `coordination_flags`.
  * IT Lead pulls initial public capital project reports for FPL and municipal utilities in South/Central Florida.
  * Backend Lead sets up the Flask boilerplate and establishes database connection strings.

### Phase 2: Core Processing & Logic (Hours 6 – 18)
* **Action Items:**
  * Implement the Google AI Studio Gemini extraction pipeline to convert unstructured project descriptions into standard spatial features (`lat`, `long`, `start_date`, `end_date`, `estimated_cost`).
  * Backend Lead writes the core cross-referencing algorithm matching projects within a 5-mile radius and overlapping date windows.
  * Frontend Lead sets up the map canvas, styling custom layers for electric transmission, gas, and civil trenching work.

### Phase 3: Integration & The "WOW" Factor (Hours 18 – 30)
* **Action Items:**
  * Wire Flask API endpoints directly to the frontend map components.
  * Build out the **Shared Trench Dollar Calculator** logic (estimating heavy machinery and labor savings based on linear footage overlap).
  * Implement the time-slider playback component allowing judges to scrub through years 2026–2030 to see construction zones illuminate.

### Phase 4: Polish, Audit Trail, & Pitch Prep (Hours 30 – 36)
* **Action Items:**
  * Add the **FERC Compliance Audit Trail** export button (generating a summary report for regulatory submission).
  * Freeze code additions. Run end-to-end integration tests using Florida test datasets.
  * Rehearse the 3-minute pitch emphasizing immediate regulatory compliance and real-world CapEx savings.

---

## 🛡️ Contingency Plans for Hackathon Roadblocks

| Roadblock / Risk | Potential Impact | Contingency / Mitigation Plan |
| :--- | :--- | :--- |
| **PDF Scraper Fails / LLM Rate Limits** | Unable to automatically parse complex utility filing documents. | **Fallback CSVs:** IT Lead maintains pre-cleaned, hardcoded JSON/CSV datasets for FPL and neighboring municipal projects that can be bulk-uploaded instantly via a manual script. |
| **PostGIS Spatial Query Latency** | Slow map rendering or timeout errors on complex spatial joins. | **Pre-Computed Flags:** Run the spatial-temporal intersection check as a database function or cron job upon data upload, rather than calculating geometries live on every frontend click. |
| **Frontend/Backend Integration Bottlenecks** | CORS errors or mismatched JSON schemas between Flask and the UI. | **Mock Data Mode:** Frontend Lead includes a toggle switch to load static mock JSON locally if the live Flask API encounters unexpected network hurdles during the final hours. |
| **Local Environment Breakage (IT Member)** | Teammate without VS Code/Homebrew loses hours setting up paths. | **Zero-Install Cloud Rule:** Enforce that the IT and Frontend leads use GitHub Codespaces or Google IDX exclusively, bypassing local machine dependency issues entirely. |

---

## ✨ The "WOW" Factor Features

1. **The Shared Trench Dollar Calculator:** Going beyond simple map pins, our engine automatically computes potential savings. If FPL and a local municipal utility are trenching the same corridor in Miami or Naples within a 60-day window, the system calculates estimated heavy machinery and labor savings (e.g., *“Coordinated Trenching Savings: $420,000”*).
2. **FERC Order 1920 Compliance Audit Trail:** A one-click export feature that compiles an executive compliance package proving interregional coordination efforts, solving an urgent regulatory pain point for utility legal teams.
3. **Time-Slider Geospatial Playback:** A dynamic timeline scrubber on the map interface that allows users to watch upcoming Florida grid construction projects evolve chronologically, highlighting conflict zones in real time.
