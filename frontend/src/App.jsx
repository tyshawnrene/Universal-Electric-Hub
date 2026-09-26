import React, { useEffect, useState } from "react";
import { CircleMarker, MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import { createClient } from "@supabase/supabase-js";
import "leaflet/dist/leaflet.css";
import "./App.css";

// Replace with your actual Supabase credentials or env variables
const supabase = createClient(import.meta.env.VITE_SUPABASE_URL, import.meta.env.VITE_SUPABASE_ANON_KEY);
const ACCENT_BLUE = "#1d84f5";
const ACCENT_GREEN = "#00afb8";
const ACCENT_PURPLE = "#9d57de";

function getProjectCoordinates(project) {
  if (!project || project.latitude == null || project.longitude == null) return null;

  const latitudeValue = String(project.latitude).trim();
  const longitudeValue = String(project.longitude).trim();
  if (!latitudeValue || !longitudeValue) return null;

  const latitude = Number(latitudeValue);
  const longitude = Number(longitudeValue);
  if (
    !Number.isFinite(latitude) ||
    !Number.isFinite(longitude) ||
    latitude < -90 ||
    latitude > 90 ||
    longitude < -180 ||
    longitude > 180
  ) {
    return null;
  }

  return [latitude, longitude];
}

function isNewProject(project, now = new Date()) {
  if (!project?.in_service_date) return false;

  const serviceDate = new Date(project.in_service_date);
  if (Number.isNaN(serviceDate.getTime())) return false;

  return (
    serviceDate.getFullYear() > now.getFullYear() ||
    (serviceDate.getFullYear() === now.getFullYear() && serviceDate.getMonth() > now.getMonth())
  );
}

function MapFocusController({ latitude, longitude }) {
  const map = useMap();

  useEffect(() => {
    if (latitude != null && longitude != null) {
      map.flyTo([latitude, longitude], Math.max(map.getZoom(), 9), { duration: 0.8 });
    }
  }, [map, latitude, longitude]);

  return null;
}

function FlagPill({ children, tone }) {
  return (
    <div
      className="ppl-flag-pill"
      style={{
        borderColor: tone,
        borderWidth: "1px",
        borderStyle: "solid",
        color: tone,
        width: "fit-content",
        padding: "0px 12px",
        borderRadius: "20px",
        fontSize: "0.75rem",
        fontWeight: "bold",
      }}
    >
      <span className="ppl-flag">{children}</span>
    </div>
  );
}

function ArrowIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12">
      <path
        d="M2.5 9.5 L9.5 2.5 M9.5 2.5 H4.5 M9.5 2.5 V7.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function App() {
  const [projects, setProjects] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ utility: "", year: "", state: "", title: "", newOnly: false });
  const [focusedProjectId, setFocusedProjectId] = useState(null);

  useEffect(() => {
    async function fetchProjects() {
      const { data, error } = await supabase.from("projects").select("*");
      if (!error && data) setProjects(data);
    }
    fetchProjects();
  }, []);

  const toggleSelect = (id) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]));
  };

  const getProjectYear = (project) => {
    if (!project.in_service_date) return "";
    const date = new Date(project.in_service_date);
    return Number.isNaN(date.getTime()) ? "" : String(date.getFullYear());
  };

  const utilityOptions = [...new Set(projects.map((p) => p.utility_company).filter(Boolean))].sort((a, b) =>
    String(a).localeCompare(String(b)),
  );
  const yearOptions = [...new Set(projects.map(getProjectYear).filter(Boolean))].sort((a, b) => Number(b) - Number(a));
  const stateOptions = [...new Set(projects.map((p) => p.state).filter(Boolean))].sort((a, b) =>
    String(a).localeCompare(String(b)),
  );
  const filteredProjects = projects.filter((project) => {
    const title = String(project.project_name ?? "").toLocaleLowerCase();
    return (
      (!filters.utility || project.utility_company === filters.utility) &&
      (!filters.year || getProjectYear(project) === filters.year) &&
      (!filters.state || project.state === filters.state) &&
      (!filters.newOnly || isNewProject(project)) &&
      (!filters.title || title.includes(filters.title.trim().toLocaleLowerCase()))
    );
  });
  const mappableProjects = filteredProjects
    .map((project) => ({ project, coordinates: getProjectCoordinates(project) }))
    .filter(({ coordinates }) => coordinates);
  const focusedProject = mappableProjects.find(({ project }) => project.id === focusedProjectId)?.project ?? null;
  const focusedCoordinates = getProjectCoordinates(focusedProject);
  const hasActiveFilters = Object.values(filters).some(Boolean);
  const updateFilter = (name, value) => setFilters((current) => ({ ...current, [name]: value }));

  const handleRunAgent = async () => {
    if (selectedIds.length < 2) {
      alert("Please select at least 2 projects to run a cross-reference analysis.");
      return;
    }
    setLoading(true);
    setReport(null);

    try {
      const response = await fetch("http://localhost:8000/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_ids: selectedIds }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Server error occurred during analysis.");
      }

      setReport(data.report);
    } catch (err) {
      console.error("Agent error details:", err);
      alert("Agent failed: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="app-shell"
      style={{
        height: "100vh",
        width: "100vw",
        left: 0,

        display: "flex",
        fontFamily: "sans-serif",
        background: "#0f172a",
        color: "#fff",
      }}
    >
      {/* Sidebar Dashboard */}
      <aside
        className="app-sidebar"
        style={{
          width: "520px",
          padding: "20px",
          background: "#111827",
          overflowY: "auto",
          borderRight: "1px solid #1f2937",
          boxSizing: "border-box",
        }}
      >
        <h2>GridSync FL</h2>
        <p style={{ color: "#9ca3af", fontSize: "0.85rem" }}>AI-Powered Transmission Infrastructure Intelligence</p>

        <button
          onClick={handleRunAgent}
          style={{
            width: "100%",
            padding: "12px",
            background: "#2563eb",
            color: "#fff",
            border: "none",
            borderRadius: "6px",
            fontWeight: "bold",
            cursor: "pointer",
            marginTop: "10px",
            marginBottom: "20px",
          }}
        >
          {loading ? "Analyzing Synergies..." : "Run AI Cross-Reference Agent"}
        </button>

        {report && (
          <div
            style={{
              background: "#1e293b",
              padding: "15px",
              borderRadius: "8px",
              marginBottom: "20px",
              border: "1px solid #3b82f6",
            }}
          >
            <h3 style={{ margin: "0 0 10px 0", color: "#60a5fa", fontSize: "1rem" }}>Strategic Action Plan</h3>
            <p style={{ fontSize: "0.8rem", lineHeight: "1.4" }}>
              <strong>Corridor Synergy:</strong> {report.spatial_and_corridor_synergy}
            </p>
            <p style={{ fontSize: "0.8rem", lineHeight: "1.4" }}>
              <strong>Schedule Alignment:</strong> {report.schedule_alignment}
            </p>
            <p style={{ fontSize: "0.8rem", lineHeight: "1.4" }}>
              <strong>Recommendations:</strong> {report.strategic_recommendations}
            </p>
          </div>
        )}

        <h4 style={{ color: "#9ca3af", textTransform: "uppercase", fontSize: "0.75rem", letterSpacing: "0.05em" }}>
          Ingested Database Records
        </h4>

        <section className="project-filters" aria-label="Filter projects">
          <div className="filter-heading">
            <span className="filter-count" aria-live="polite">
              Showing {filteredProjects.length} of {projects.length} projects · {selectedIds.length} selected
            </span>
            {hasActiveFilters && (
              <button
                type="button"
                className="clear-filters"
                onClick={() => setFilters({ utility: "", year: "", state: "", title: "", newOnly: false })}
              >
                Clear filters
              </button>
            )}
          </div>
          <label className="filter-field filter-search">
            <span>Search project title</span>
            <input
              type="search"
              value={filters.title}
              onChange={(event) => updateFilter("title", event.target.value)}
              placeholder="Search by title..."
            />
          </label>
          <div className="filter-grid">
            <label className="filter-field">
              <span>Utility company</span>
              <select value={filters.utility} onChange={(event) => updateFilter("utility", event.target.value)}>
                <option value="">All utilities</option>
                {utilityOptions.map((utility) => (
                  <option key={utility} value={utility}>
                    {utility}
                  </option>
                ))}
              </select>
            </label>
            <label className="filter-field">
              <span>In-service year</span>
              <select value={filters.year} onChange={(event) => updateFilter("year", event.target.value)}>
                <option value="">All years</option>
                {yearOptions.map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
            </label>
            <label className="filter-field">
              <span>State</span>
              <select value={filters.state} onChange={(event) => updateFilter("state", event.target.value)}>
                <option value="">All states</option>
                {stateOptions.map((state) => (
                  <option key={state} value={state}>
                    {state}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="new-project-filter">
            <input
              type="checkbox"
              checked={filters.newOnly}
              onChange={(event) => updateFilter("newOnly", event.target.checked)}
            />
            <span>New projects only</span>
          </label>
        </section>

        <button
          type="button"
          className="clear-selection-button"
          onClick={() => setSelectedIds([])}
          disabled={selectedIds.length === 0}
        >
          Clear selected projects ({selectedIds.length})
        </button>

        <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: "10px" }}>
          {filteredProjects.length ? (
            filteredProjects.map((p) => (
              <div key={p.id}>
                <div
                  className="ppl-project"
                  style={{
                    transition: "border-left 0.1s ease",
                    display: "flex",
                    gap: "12px",
                    borderColor: ACCENT_BLUE,
                    borderWidth: "1px",
                    borderStyle: "solid",
                    borderRadius: "8px",
                    padding: "12px",
                    borderLeft: selectedIds.includes(p.id) ? "5px solid " + ACCENT_BLUE : "1px solid " + ACCENT_BLUE,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(p.id)}
                    onChange={() => toggleSelect(p.id)}
                    style={{ marginTop: "4px", cursor: "pointer" }}
                  />
                  <div>
                    <div
                      className="ppl-project-head"
                      style={{ display: "flex", flexDirection: "column", alignItems: "left" }}
                    >
                      <div
                        className="ppl-project-title-row"
                        style={{ display: "flex", flexDirection: "column", gap: "2px" }}
                      >
                        <h3
                          className="ppl-project-name"
                          style={{ textAlign: "left", fontSize: "1.25rem", fontWeight: "bold", margin: 0 }}
                        >
                          {p.project_name}
                        </h3>
                        <p className="ppl-project-meta" style={{ textAlign: "left" }}>
                          {p.utility_company}
                        </p>
                        <div
                          className="ppl-project-badges"
                          style={{ display: "flex", flexDirection: "row", gap: "4px", flexWrap: "wrap" }}
                        >
                          {p.in_service_date && (
                            <FlagPill tone={ACCENT_GREEN}>{new Date(p.in_service_date).getFullYear()}</FlagPill>
                          )}
                          {p.state && <FlagPill tone={ACCENT_PURPLE}>{p.state}</FlagPill>}
                          {isNewProject(p) && <FlagPill tone={ACCENT_BLUE}>New</FlagPill>}
                        </div>
                        <p
                          className="ppl-project-meta"
                          style={{ textAlign: "left", fontSize: "0.8rem", color: "#9ca3af" }}
                        >
                          {p.project_scope}
                        </p>
                      </div>

                      <button
                        type="button"
                        className="ppl-go-btn"
                        onClick={() => setFocusedProjectId(p.id)}
                        disabled={!getProjectCoordinates(p)}
                        aria-label={`Show ${p.project_name} on map`}
                        style={{
                          width: "fit-content",
                          padding: "10px 15px",
                          background: ACCENT_BLUE,
                          color: "#fff",
                          border: "none",
                          borderRadius: "12px",
                          fontWeight: "bold",
                          cursor: "pointer",
                          marginTop: "10px",
                          marginBottom: "20px",
                          fontSize: "0.8rem",
                        }}
                      >
                        <span>Go</span>
                        <ArrowIcon />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))
          ) : (
            <p className="empty-projects" role="status">
              {projects.length ? "No projects match these filters." : "No project records found."}
            </p>
          )}
        </div>
      </aside>

      {/* Map View */}
      <div style={{ flex: 1, height: "100%" }}>
        <MapContainer center={[32.74, -79.93]} zoom={6} style={{ height: "100%", width: "100%" }}>
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution="&copy; OpenStreetMap contributors"
          />
          <MapFocusController latitude={focusedCoordinates?.[0]} longitude={focusedCoordinates?.[1]} />
          {mappableProjects.map(({ project, coordinates }) => (
            <React.Fragment key={project.id}>
              {project.id === focusedProjectId && (
                <CircleMarker
                  center={coordinates}
                  radius={22}
                  pathOptions={{
                    color: "#60a5fa",
                    weight: 3,
                    opacity: 0.95,
                    fillColor: "#3b82f6",
                    fillOpacity: 0.2,
                  }}
                  interactive={false}
                />
              )}
              <Marker position={coordinates}>
                <Popup>
                  <div style={{ maxWidth: "220px" }}>
                    <strong>{project.project_name}</strong>
                    <br />
                    <p style={{ margin: "5px 0", fontSize: "0.85rem" }}>{project.project_scope}</p>
                    <em style={{ fontSize: "0.75rem" }}>Utility: {project.utility_company}</em>
                  </div>
                </Popup>
              </Marker>
            </React.Fragment>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}
