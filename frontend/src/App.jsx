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
const OVERLAP_TIER_COLORS = {
  "under_1.6km": "#facc15",
  under_8km: "#22c55e",
  under_40km: "#1d84f5",
  unclassified: "#1d84f5",
};
const COLOCATED_FLAG_ICON = L.divIcon({
  className: "colocated-flag-icon",
  html: '<span aria-hidden="true">🚩</span>',
  iconSize: [28, 30],
  iconAnchor: [14, 28],
});
const FOCUSED_COLOCATED_FLAG_ICON = L.divIcon({
  className: "colocated-flag-icon is-focused",
  html: '<span aria-hidden="true">🚩</span>',
  iconSize: [36, 38],
  iconAnchor: [18, 35],
});

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

function MapFocusController({ latitude, longitude, pairStart, pairEnd }) {
  const map = useMap();
  const pairStartLat = pairStart?.[0];
  const pairStartLng = pairStart?.[1];
  const pairEndLat = pairEnd?.[0];
  const pairEndLng = pairEnd?.[1];

  useEffect(() => {
    if (pairStartLat != null && pairStartLng != null && pairEndLat != null && pairEndLng != null) {
      const start = [pairStartLat, pairStartLng];
      const end = [pairEndLat, pairEndLng];
      if (pairStartLat === pairEndLat && pairStartLng === pairEndLng) {
        map.flyTo(start, Math.max(map.getZoom(), 12), { duration: 0.8 });
      } else {
        map.fitBounds(L.latLngBounds(start, end), { padding: [72, 72], maxZoom: 10, duration: 0.8 });
      }
    } else if (latitude != null && longitude != null) {
      map.flyTo([latitude, longitude], Math.max(map.getZoom(), 9), { duration: 0.8 });
    }
  }, [map, latitude, longitude, pairStartLat, pairStartLng, pairEndLat, pairEndLng]);

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

function ProjectCard({
  project,
  selected,
  onToggleSelect,
  onFocus,
  showSelection = true,
  showFocus = true,
  compact = false,
}) {
  const year = parseServiceDate(project)?.getFullYear();

  return (
    <article
      className={`ppl-project${compact ? " overlap-project-card" : ""}`}
      style={{
        transition: "border-left 0.1s ease",
        display: "flex",
        gap: "12px",
        borderColor: ACCENT_BLUE,
        borderWidth: "1px",
        borderStyle: "solid",
        borderRadius: "8px",
        padding: "12px",
        borderLeft: selected ? `5px solid ${ACCENT_BLUE}` : `1px solid ${ACCENT_BLUE}`,
      }}
    >
      {showSelection && (
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggleSelect(project.id)}
          aria-label={`Select ${project.name}`}
          style={{ marginTop: "4px", cursor: "pointer" }}
        />
      )}
      <div className="project-card-content">
        <h3
          className="ppl-project-name"
          style={{ textAlign: "left", fontSize: "1.25rem", fontWeight: "bold", margin: 0 }}
        >
          {project.name}
        </h3>
        <p className="ppl-project-meta" style={{ textAlign: "left" }}>
          {project.utility}
        </p>
        <div
          className="ppl-project-badges"
          style={{ display: "flex", flexDirection: "row", gap: "4px", flexWrap: "wrap" }}
        >
          {year && <FlagPill tone={ACCENT_GREEN}>{year}</FlagPill>}
          {project.state && <FlagPill tone={ACCENT_PURPLE}>{project.state}</FlagPill>}
          {isNewProject(project) && <FlagPill tone={ACCENT_BLUE}>New</FlagPill>}
        </div>
        <p
          className={`ppl-project-meta ${compact ? "overlap-project-scope" : "project-scope"}`}
          style={{ textAlign: "left", fontSize: "0.8rem", color: "#9ca3af" }}
        >
          {project.scope}
        </p>
        {showFocus && (
          <button
            type="button"
            className="ppl-go-btn"
            onClick={() => onFocus(project.id)}
            disabled={!getProjectCoordinates(project)}
            aria-label={`Show ${project.name} on map`}
            style={{
              width: "fit-content",
              padding: "10px 15px",
              background: ACCENT_BLUE,
              color: "#fff",
              border: "none",
              borderRadius: "12px",
              fontWeight: "bold",
              cursor: "pointer",
              fontSize: "0.8rem",
            }}
          >
            <span>Show</span>
            <ArrowIcon />
          </button>
        )}
      </div>
    </article>
  );
}

export default function App() {
  const [projects, setProjects] = useState([]);
  const [projectsError, setProjectsError] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [selectedPairKeys, setSelectedPairKeys] = useState([]);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ utility: "", year: "", state: "", title: "", newOnly: false });
  const [focusedProjectId, setFocusedProjectId] = useState(null);
  const [focusedPairKey, setFocusedPairKey] = useState(null);
  const [displayMode, setDisplayMode] = useState("overlaps");
  const [pairMatchMode, setPairMatchMode] = useState("or");
  const [overlapCategory, setOverlapCategory] = useState("all");
  const [differentCompaniesOnly, setDifferentCompaniesOnly] = useState(true);
  const [overlaps, setOverlaps] = useState([]);
  const [overlapsLoading, setOverlapsLoading] = useState(true);
  const [overlapsError, setOverlapsError] = useState(null);
  const [overlapsRetry, setOverlapsRetry] = useState(0);
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
    if (displayMode !== "overlaps") return undefined;

    let cancelled = false;
    fetchOverlaps()
      .then((data) => {
        if (!cancelled) setOverlaps(data.overlaps ?? []);
      })
      .catch((error) => {
        if (!cancelled) setOverlapsError(error.message);
      })
      .finally(() => {
        if (!cancelled) setOverlapsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [displayMode, overlapsRetry]);

  useEffect(() => {
    fetchProjects()
      .then((data) => {
        setProjects(data.projects);
        setProjectsError(null);
      })
      .catch((err) => {
        console.error("Failed to load projects:", err);
        setProjectsError(err.message);
      });
  }, []);

  const toggleSelect = (id) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]));
  };

  const togglePairSelection = (pairKey) => {
    setSelectedPairKeys((previous) =>
      previous.includes(pairKey) ? previous.filter((key) => key !== pairKey) : [...previous, pairKey],
    );
  };

  const openOverlapsMode = () => {
    setDisplayMode("overlaps");
    setOverlapsLoading(true);
    setOverlapsError(null);
    setOverlapsRetry((retry) => retry + 1);
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
  const matchesProjectFilters = (project) => {
    const title = String(project.name ?? "").toLocaleLowerCase();
    return (
      (!filters.utility || project.utility === filters.utility) &&
      (!filters.year || getProjectYear(project) === filters.year) &&
      (!filters.state || project.state === filters.state) &&
      (!filters.newOnly || isNewProject(project)) &&
      (!filters.title || title.includes(filters.title.trim().toLocaleLowerCase()))
    );
  };
  const filteredProjects = projects.filter(matchesProjectFilters);
  const projectsById = new Map(projects.map((project) => [String(project.id), project]));
  const filteredProjectIds = new Set(filteredProjects.map((project) => String(project.id)));
  const matchesOverlapCategory = (pair, projectA, projectB) => {
    const coordinatesA = getProjectCoordinates(projectA);
    const coordinatesB = getProjectCoordinates(projectB);
    const sameLocation =
      coordinatesA && coordinatesB && coordinatesA[0] === coordinatesB[0] && coordinatesA[1] === coordinatesB[1];
    const distance = Number(pair.distance_km);

    if (overlapCategory === "exact") return sameLocation;
    if (overlapCategory === "under_1.6km") return !sameLocation && pair.tier === "under_1.6km";
    if (overlapCategory === "1.6_to_8km") return pair.tier === "under_8km";
    if (overlapCategory === "8_to_40km") {
      return pair.tier === "under_40km" || (pair.tier == null && Number.isFinite(distance) && distance === 40);
    }
    return true;
  };
  const resolvedOverlapPairs = overlaps.flatMap((pair) => {
    const projectA = projectsById.get(String(pair.project_a?.id));
    const projectB = projectsById.get(String(pair.project_b?.id));
    if (!projectA || !projectB) return [];

    const projectIds = [String(projectA.id), String(projectB.id)].sort();
    return [{ ...pair, projectA, projectB, key: projectIds.join("::") }];
  });
  const visibleOverlapPairs = resolvedOverlapPairs.filter((pair) => {
    const matchesA = filteredProjectIds.has(String(pair.projectA.id));
    const matchesB = filteredProjectIds.has(String(pair.projectB.id));
    const pairMatches = pairMatchMode === "and" ? matchesA && matchesB : matchesA || matchesB;
    return (
      pairMatches &&
      (!differentCompaniesOnly || pair.cross_utility === true) &&
      matchesOverlapCategory(pair, pair.projectA, pair.projectB)
    );
  });
  const mapDisplayProjects = selectedIds.length
    ? filteredProjects.filter((project) => selectedIds.includes(project.id) || project.id === focusedProjectId)
    : filteredProjects;
  const mapDisplayOverlapPairs = selectedPairKeys.length
    ? visibleOverlapPairs.filter((pair) => selectedPairKeys.includes(pair.key) || pair.key === focusedPairKey)
    : visibleOverlapPairs;
  const selectedPairProjectIds = [
    ...new Set(
      resolvedOverlapPairs
        .filter((pair) => selectedPairKeys.includes(pair.key))
        .flatMap((pair) => [String(pair.projectA.id), String(pair.projectB.id)]),
    ),
  ];
  const activeSelectionCount = displayMode === "projects" ? selectedIds.length : selectedPairKeys.length;
  const activeProjectIds = displayMode === "projects" ? selectedIds : selectedPairProjectIds;
  const overlapProjects = [
    ...new Map(
      mapDisplayOverlapPairs
        .flatMap((pair) => [pair.projectA, pair.projectB])
        .map((project) => [String(project.id), project]),
    ).values(),
  ];
  const mapProjects = displayMode === "overlaps" ? overlapProjects : mapDisplayProjects;
  const mappableProjects = mapProjects
    .map((project) => ({ project, coordinates: getProjectCoordinates(project) }))
    .filter(({ coordinates }) => coordinates);
  const overlapMapPairs =
    displayMode === "overlaps"
      ? mapDisplayOverlapPairs.flatMap((pair) => {
          const coordinatesA = getProjectCoordinates(pair.projectA);
          const coordinatesB = getProjectCoordinates(pair.projectB);
          if (!coordinatesA || !coordinatesB) return [];

          return [
            {
              ...pair,
              coordinatesA,
              coordinatesB,
              sameLocation: coordinatesA[0] === coordinatesB[0] && coordinatesA[1] === coordinatesB[1],
              color: OVERLAP_TIER_COLORS[pair.tier] ?? OVERLAP_TIER_COLORS.unclassified,
            },
          ];
        })
      : [];
  const colocatedProjectsByLocation = new Map();
  overlapMapPairs
    .filter((pair) => pair.sameLocation)
    .forEach((pair) => {
      const locationKey = pair.coordinatesA.join(",");
      const colocated = colocatedProjectsByLocation.get(locationKey) ?? {
        coordinates: pair.coordinatesA,
        projects: new Map(),
      };
      colocated.projects.set(String(pair.projectA.id), pair.projectA);
      colocated.projects.set(String(pair.projectB.id), pair.projectB);
      colocatedProjectsByLocation.set(locationKey, colocated);
    });
  const focusedProject = mappableProjects.find(({ project }) => project.id === focusedProjectId)?.project ?? null;
  const focusedCoordinates = getProjectCoordinates(focusedProject);
  const focusedPair = overlapMapPairs.find((pair) => pair.key === focusedPairKey) ?? null;
  const focusedPairCoordinates = focusedPair ? [focusedPair.coordinatesA, focusedPair.coordinatesB] : null;
  const hasActiveFilters =
    Object.values(filters).some(Boolean) ||
    (displayMode === "overlaps" && (overlapCategory !== "all" || differentCompaniesOnly));
  const updateFilter = (name, value) => setFilters((current) => ({ ...current, [name]: value }));

  const handleRunAgent = async () => {
    if (activeProjectIds.length < 2) {
      alert("Please select at least 2 projects to run a cross-reference analysis.");
      return;
    }
    setLoading(true);
    setReport(null);

    try {
      const data = await runCoordinationReport(activeProjectIds);
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

        <div className="display-mode-switch" role="group" aria-label="Project display mode">
          <button type="button" aria-pressed={displayMode === "overlaps"} onClick={openOverlapsMode}>
            Overlaps
          </button>
          <button type="button" aria-pressed={displayMode === "projects"} onClick={() => setDisplayMode("projects")}>
            Projects
          </button>
        </div>

        <section className="project-filters" aria-label="Filter projects">
          <div className="filter-heading">
            <span className="filter-count" aria-live="polite">
              {displayMode === "projects"
                ? `Showing ${filteredProjects.length} of ${projects.length} projects · ${selectedIds.length} selected`
                : `Showing ${visibleOverlapPairs.length} overlap pairs · ${activeSelectionCount} selected`}
            </span>
            {hasActiveFilters && (
              <button
                type="button"
                className="clear-filters"
                onClick={() => {
                  setFilters({ utility: "", year: "", state: "", title: "", newOnly: false });
                  setOverlapCategory("all");
                  setDifferentCompaniesOnly(false);
                }}
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
          {displayMode === "overlaps" && (
            <label className="filter-field pair-match-field">
              <span>Pair matches filters when</span>
              <select value={pairMatchMode} onChange={(event) => setPairMatchMode(event.target.value)}>
                <option value="and">Both projects match (AND)</option>
                <option value="or">Either project matches (OR)</option>
              </select>
            </label>
          )}
          {displayMode === "overlaps" && (
            <label className="filter-field pair-match-field">
              <span>Overlap distance category</span>
              <select value={overlapCategory} onChange={(event) => setOverlapCategory(event.target.value)}>
                <option value="all">All categories</option>
                <option value="exact">Exact location</option>
                <option value="under_1.6km">Under 1.6 km</option>
                <option value="1.6_to_8km">1.6 to under 8 km</option>
                <option value="8_to_40km">8 to 40 km</option>
              </select>
            </label>
          )}
          {displayMode === "overlaps" && (
            <label className="new-project-filter">
              <input
                type="checkbox"
                checked={differentCompaniesOnly}
                onChange={(event) => setDifferentCompaniesOnly(event.target.checked)}
              />
              <span>Different companies only</span>
            </label>
          )}
        </section>

        <button
          type="button"
          className="clear-selection-button"
          onClick={() => (displayMode === "projects" ? setSelectedIds([]) : setSelectedPairKeys([]))}
          disabled={activeSelectionCount === 0}
        >
          {displayMode === "projects" ? "Clear selected projects" : "Clear selected pairs"} ({activeSelectionCount})
        </button>

        <div className="project-results">
          {displayMode === "projects" &&
            filteredProjects.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                selected={selectedIds.includes(project.id)}
                onToggleSelect={toggleSelect}
                onFocus={setFocusedProjectId}
              />
            ))}
          {displayMode === "overlaps" && overlapsLoading && (
            <p className="empty-projects" role="status">
              Loading overlap pairs…
            </p>
          )}
          {displayMode === "overlaps" && overlapsError && (
            <div className="empty-projects" role="alert">
              <p>Couldn’t load overlap pairs: {overlapsError}</p>
              <button type="button" className="clear-filters" onClick={() => setOverlapsRetry((count) => count + 1)}>
                Try again
              </button>
            </div>
          )}
          {displayMode === "overlaps" &&
            !overlapsLoading &&
            !overlapsError &&
            visibleOverlapPairs.map((pair) => (
              <section
                className={`overlap-pair${selectedPairKeys.includes(pair.key) ? " is-pair-selected" : ""}`}
                key={pair.key}
                aria-label={`${pair.projectA.name} and ${pair.projectB.name}`}
              >
                <div className="overlap-pair-actions">
                  <button
                    type="button"
                    className="ppl-go-btn overlap-pair-go"
                    onClick={() => setFocusedPairKey(pair.key)}
                    disabled={!getProjectCoordinates(pair.projectA) || !getProjectCoordinates(pair.projectB)}
                    aria-label={`Show overlap between ${pair.projectA.name} and ${pair.projectB.name} on map`}
                  >
                    <span>Show pair on map</span>
                    <ArrowIcon />
                  </button>
                  <label className="overlap-pair-selection">
                    <input
                      type="checkbox"
                      checked={selectedPairKeys.includes(pair.key)}
                      onChange={() => togglePairSelection(pair.key)}
                      aria-label={`Select pair: ${pair.projectA.name} and ${pair.projectB.name}`}
                    />
                    <span>Select pair</span>
                  </label>
                </div>
                <ProjectCard
                  project={pair.projectA}
                  selected={selectedPairKeys.includes(pair.key)}
                  onToggleSelect={toggleSelect}
                  onFocus={setFocusedProjectId}
                  showSelection={false}
                  showFocus={false}
                  compact
                />
                <div className="pair-connector" aria-label={`${Number(pair.distance_km).toFixed(2)} kilometers apart`}>
                  <div className="pair-distance">{Number(pair.distance_km).toFixed(2)} km</div>
                </div>
                <ProjectCard
                  project={pair.projectB}
                  selected={selectedPairKeys.includes(pair.key)}
                  onToggleSelect={toggleSelect}
                  onFocus={setFocusedProjectId}
                  showSelection={false}
                  showFocus={false}
                  compact
                />
              </section>
            ))}
          {((displayMode === "projects" && filteredProjects.length === 0) ||
            (displayMode === "overlaps" && !overlapsLoading && !overlapsError && visibleOverlapPairs.length === 0)) && (
            <p className="empty-projects" role="status">
              {displayMode === "overlaps"
                ? overlaps.length
                  ? "No overlap pairs match the current filters and pair rule."
                  : "No overlap pairs were found within 40 km."
                : projectsError
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
        {displayMode === "overlaps" && (
          <div className="overlap-map-legend" aria-label="Overlap map legend">
            <strong>Overlap distance</strong>
            <span>
              <i style={{ backgroundColor: OVERLAP_TIER_COLORS["under_1.6km"] }} />
              Under 1.6 km
            </span>
            <span>
              <i style={{ backgroundColor: OVERLAP_TIER_COLORS.under_8km }} />
              1.6 to under 8 km
            </span>
            <span>
              <i style={{ backgroundColor: OVERLAP_TIER_COLORS.under_40km }} />8 to 40 km
            </span>
            <span>
              <b aria-hidden="true">🚩</b>Same location
            </span>
          </div>
        )}
        <MapContainer center={[32.74, -79.93]} zoom={6} style={{ height: "100%", width: "100%" }}>
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution="&copy; OpenStreetMap contributors"
          />
          <MapResizeObserver />
          <MapFocusController
            latitude={displayMode === "projects" ? focusedCoordinates?.[0] : undefined}
            longitude={displayMode === "projects" ? focusedCoordinates?.[1] : undefined}
            pairStart={displayMode === "overlaps" ? focusedPairCoordinates?.[0] : null}
            pairEnd={displayMode === "overlaps" ? focusedPairCoordinates?.[1] : null}
          />
          {overlapMapPairs
            .filter((pair) => !pair.sameLocation)
            .slice()
            .sort((a, b) => {
              if (a.key === focusedPairKey) return 1;
              if (b.key === focusedPairKey) return -1;
              return Number(b.distance_km) - Number(a.distance_km);
            })
            .map((pair) => (
              <Polyline
                key={`overlap-line-${pair.key}`}
                positions={[pair.coordinatesA, pair.coordinatesB]}
                pathOptions={{
                  color: pair.color,
                  weight: pair.key === focusedPairKey ? 7 : 2,
                  opacity: pair.key === focusedPairKey ? 1 : 0.9,
                }}
              />
            ))}
          {mappableProjects.map(({ project, coordinates }) => (
            <React.Fragment key={project.id}>
              {((displayMode === "projects" && project.id === focusedProjectId) ||
                (focusedPair && [focusedPair.projectA.id, focusedPair.projectB.id].includes(project.id))) && (
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
              <Marker
                position={coordinates}
                zIndexOffset={
                  focusedPair && [focusedPair.projectA.id, focusedPair.projectB.id].includes(project.id) ? 500 : 0
                }
              >
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
          {[...colocatedProjectsByLocation.entries()].map(([locationKey, colocated]) => (
            <Marker
              key={`colocated-${locationKey}`}
              position={colocated.coordinates}
              icon={
                focusedPair &&
                [focusedPair.projectA.id, focusedPair.projectB.id].every((id) => colocated.projects.has(String(id)))
                  ? FOCUSED_COLOCATED_FLAG_ICON
                  : COLOCATED_FLAG_ICON
              }
            >
              <Popup>
                <div>
                  <strong>Projects at the same location</strong>
                  <ul className="colocated-project-list">
                    {[...colocated.projects.values()].map((project) => (
                      <li key={project.id}>
                        {project.name}
                        {project.utility ? ` — ${project.utility}` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}
