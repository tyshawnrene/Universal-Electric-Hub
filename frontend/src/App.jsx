import React, { useEffect, useRef, useState } from "react";
import { CircleMarker, MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerIconRetina from "leaflet/dist/images/marker-icon-2x.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import { fetchOverlaps, fetchProjects, runCoordinationReport } from "./api";
import "./App.css";

L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIconRetina,
  shadowUrl: markerShadow,
});

const ACCENT_BLUE = "#1d84f5";
const ACCENT_GREEN = "#00afb8";
const ACCENT_PURPLE = "#9d57de";
const OVERLAP_RENDERER = L.canvas({ padding: 0.5 });

// The backend sends dates as "YYYY-MM-DD". new Date() would read that as UTC midnight,
// which is the previous day in US time zones, so build a local date instead.
function parseServiceDate(project) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(project?.in_service_date ?? "");
  return match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])) : null;
}

function getProjectCoordinates(project) {
  if (!project || project.lat == null || project.lng == null) return null;

  const latitudeValue = String(project.lat).trim();
  const longitudeValue = String(project.lng).trim();
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
  const serviceDate = parseServiceDate(project);
  if (!serviceDate) return false;

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

function MapResizeObserver() {
  const map = useMap();

  useEffect(() => {
    const container = map.getContainer();
    const observer = new ResizeObserver(() => map.invalidateSize({ pan: false, debounceMoveend: true }));
    observer.observe(container);
    return () => observer.disconnect();
  }, [map]);

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
  const [projectsError, setProjectsError] = useState(null);
  const [overlaps, setOverlaps] = useState([]);
  const [overlapsError, setOverlapsError] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ utility: "", year: "", state: "", title: "", newOnly: false });
  const [focusedProjectId, setFocusedProjectId] = useState(null);
  const [sidebarWidth, setSidebarWidth] = useState(520);
  const resizingRef = useRef(false);

  const clampSidebarWidth = (width) => {
    const minimum = 300;
    const maximum = Math.max(minimum, Math.min(window.innerWidth * 0.65, window.innerWidth - 260));
    return Math.min(Math.max(width, minimum), maximum);
  };

  const handleSplitterPointerDown = (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    resizingRef.current = true;
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handleSplitterPointerMove = (event) => {
    if (resizingRef.current) setSidebarWidth(clampSidebarWidth(event.clientX));
  };

  const stopSplitterResize = () => {
    resizingRef.current = false;
  };

  const handleSplitterKeyDown = (event) => {
    const step = event.shiftKey ? 50 : 20;
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      setSidebarWidth((width) => clampSidebarWidth(width - step));
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      setSidebarWidth((width) => clampSidebarWidth(width + step));
    } else if (event.key === "Home") {
      event.preventDefault();
      setSidebarWidth(clampSidebarWidth(300));
    } else if (event.key === "End") {
      event.preventDefault();
      setSidebarWidth(clampSidebarWidth(window.innerWidth * 0.65));
    }
  };

  useEffect(() => {
    const keepSidebarInBounds = () => {
      if (window.innerWidth <= 760) return;
      const maximum = Math.max(300, Math.min(window.innerWidth * 0.65, window.innerWidth - 260));
      setSidebarWidth((width) => Math.min(Math.max(width, 300), maximum));
    };

    keepSidebarInBounds();
    window.addEventListener("resize", keepSidebarInBounds);
    return () => window.removeEventListener("resize", keepSidebarInBounds);
  }, []);

  useEffect(() => {
    Promise.all([fetchProjects(), fetchOverlaps()])
      .then(([projectData, overlapData]) => {
        setProjects(projectData.projects ?? []);
        setOverlaps(overlapData.overlaps ?? []);
        setProjectsError(projectData.errors?.length ? "Some project records could not be normalized." : null);
        setOverlapsError(overlapData.errors?.length ? "Some overlap records could not be normalized." : null);
      })
      .catch((err) => {
        console.error("Failed to load dashboard data:", err);
        setProjectsError(err.message);
        setOverlapsError(err.message);
      });
  }, []);

  const toggleSelect = (id) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]));
  };

  const getProjectYear = (project) => {
    const date = parseServiceDate(project);
    return date ? String(date.getFullYear()) : "";
  };

  const utilityOptions = [...new Set(projects.map((p) => p.utility).filter(Boolean))].sort((a, b) =>
    String(a).localeCompare(String(b)),
  );
  const yearOptions = [...new Set(projects.map(getProjectYear).filter(Boolean))].sort((a, b) => Number(b) - Number(a));
  const stateOptions = [...new Set(projects.map((p) => p.state).filter(Boolean))].sort((a, b) =>
    String(a).localeCompare(String(b)),
  );
  const filteredProjects = projects.filter((project) => {
    const title = String(project.name ?? "").toLocaleLowerCase();
    return (
      (!filters.utility || project.utility === filters.utility) &&
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
  const projectCoordinates = new Map(
    mappableProjects.map(({ project, coordinates }) => [String(project.id), coordinates]),
  );
  const visibleOverlaps = overlaps
    .map((overlap) => ({
      overlap,
      start: projectCoordinates.get(String(overlap.project_a.id)),
      end: projectCoordinates.get(String(overlap.project_b.id)),
    }))
    .filter(({ start, end }) => start && end);
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
      const data = await runCoordinationReport(selectedIds);
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
        "--sidebar-width": `${sidebarWidth}px`,
        fontFamily: "sans-serif",
        background: "#0f172a",
        color: "#fff",
      }}
    >
      {/* Sidebar Dashboard */}
      <aside
        className="app-sidebar"
        style={{
          padding: "20px",
          background: "#111827",
          overflowY: "auto",
          borderRight: "1px solid #1f2937",
          boxSizing: "border-box",
        }}
      >
        <h2 style={{ color: "#850ffa", fontSize: "0.85rem" }}>GridSync</h2>
        <h3>Dashboard</h3>
        <p style={{ color: "#edecee", fontSize: "0.85rem" }}>AI-Powered Transmission Infrastructure Intelligence</p>

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
                          {p.name}
                        </h3>
                        <p className="ppl-project-meta" style={{ textAlign: "left" }}>
                          {p.utility}
                        </p>
                        <div
                          className="ppl-project-badges"
                          style={{ display: "flex", flexDirection: "row", gap: "4px", flexWrap: "wrap" }}
                        >
                          {getProjectYear(p) && <FlagPill tone={ACCENT_GREEN}>{getProjectYear(p)}</FlagPill>}
                          {p.state && <FlagPill tone={ACCENT_PURPLE}>{p.state}</FlagPill>}
                          {isNewProject(p) && <FlagPill tone={ACCENT_BLUE}>New</FlagPill>}
                        </div>
                        <p
                          className="ppl-project-meta"
                          style={{ textAlign: "left", fontSize: "0.8rem", color: "#9ca3af" }}
                        >
                          {p.scope}
                          {p.project_type && ` Type: ${p.project_type}.`}
                          {p.estimated_cost != null && ` Estimated cost: $${Number(p.estimated_cost).toLocaleString()}.`}
                        </p>
                      </div>

                      <button
                        type="button"
                        className="ppl-go-btn"
                        onClick={() => setFocusedProjectId(p.id)}
                        disabled={!getProjectCoordinates(p)}
                        aria-label={`Show ${p.name} on map`}
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
              {projectsError
                ? `Couldn't load projects from the backend: ${projectsError}`
                : projects.length
                  ? "No projects match these filters."
                  : "No project records found."}
            </p>
          )}
        </div>
      </aside>

      <div
        className="sidebar-splitter"
        role="separator"
        aria-label="Resize project panel"
        aria-orientation="vertical"
        aria-valuemin={300}
        aria-valuemax={Math.floor(Math.max(300, Math.min(window.innerWidth * 0.65, window.innerWidth - 260)))}
        aria-valuenow={Math.round(sidebarWidth)}
        tabIndex={0}
        onKeyDown={handleSplitterKeyDown}
        onPointerDown={handleSplitterPointerDown}
        onPointerMove={handleSplitterPointerMove}
        onPointerUp={stopSplitterResize}
        onPointerCancel={stopSplitterResize}
        onLostPointerCapture={stopSplitterResize}
      >
        <span aria-hidden="true" />
      </div>

      {/* Map View */}
      <div className="map-pane">
        <MapContainer
          center={[32.74, -79.93]}
          zoom={6}
          preferCanvas
          style={{ height: "100%", width: "100%" }}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution="&copy; OpenStreetMap contributors"
          />
          <MapResizeObserver />
          <MapFocusController latitude={focusedCoordinates?.[0]} longitude={focusedCoordinates?.[1]} />
          {visibleOverlaps.map(({ overlap, start, end }) => (
            <Polyline
              key={`${overlap.project_a.id}-${overlap.project_b.id}`}
              positions={[start, end]}
              pathOptions={{
                color: overlap.cross_utility ? "#f97316" : "#64748b",
                opacity: 0.8,
                weight: overlap.cross_utility ? 3 : 2,
                pane: "overlayPane",
              }}
              renderer={OVERLAP_RENDERER}
              interactive={false}
            />
          ))}
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
                    <strong>{project.name}</strong>
                    <br />
                    <p style={{ margin: "5px 0", fontSize: "0.85rem" }}>{project.scope}</p>
                    <em style={{ fontSize: "0.75rem" }}>Utility: {project.utility}</em>
                  </div>
                </Popup>
              </Marker>
            </React.Fragment>
          ))}
        </MapContainer>
        {overlapsError && <p className="map-data-error">{overlapsError}</p>}
      </div>
    </div>
  );
}
