import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import { createClient } from '@supabase/supabase-js';
import 'leaflet/dist/leaflet.css';

// Replace with your actual Supabase credentials or env variables
const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL, 
  import.meta.env.VITE_SUPABASE_ANON_KEY
);

export default function App() {
  const [projects, setProjects] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function fetchProjects() {
      const { data, error } = await supabase.from('projects').select('*');
      if (!error && data) setProjects(data);
    }
    fetchProjects();
  }, []);

  const toggleSelect = (id) => {
    setSelectedIds(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const handleRunAgent = async () => {
    if (selectedIds.length < 2) {
      alert("Please select at least 2 projects to run a cross-reference analysis.");
      return;
    }
    setLoading(true);
    setReport(null);

    try {
      const response = await fetch('http://localhost:8000/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_ids: selectedIds })
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
    <div style={{ height: '100vh', width: '100vw', display: 'flex', fontFamily: 'sans-serif', background: '#0f172a', color: '#fff' }}>
      {/* Sidebar Dashboard */}
      <div style={{ width: '420px', padding: '20px', background: '#111827', overflowY: 'auto', borderRight: '1px solid #1f2937', boxSizing: 'border-box' }}>
        <h2>GridSync FL</h2>
        <p style={{ color: '#9ca3af', fontSize: '0.85rem' }}>AI-Powered Transmission Infrastructure Intelligence</p>
        
        <button 
          onClick={handleRunAgent}
          style={{ width: '100%', padding: '12px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: 'bold', cursor: 'pointer', marginTop: '10px', marginBottom: '20px' }}>
          {loading ? 'Analyzing Synergies...' : 'Run AI Cross-Reference Agent'}
        </button>

        {report && (
          <div style={{ background: '#1e293b', padding: '15px', borderRadius: '8px', marginBottom: '20px', border: '1px solid #3b82f6' }}>
            <h3 style={{ margin: '0 0 10px 0', color: '#60a5fa', fontSize: '1rem' }}>Strategic Action Plan</h3>
            <p style={{ fontSize: '0.8rem', lineHeight: '1.4' }}><strong>Corridor Synergy:</strong> {report.spatial_and_corridor_synergy}</p>
            <p style={{ fontSize: '0.8rem', lineHeight: '1.4' }}><strong>Schedule Alignment:</strong> {report.schedule_alignment}</p>
            <p style={{ fontSize: '0.8rem', lineHeight: '1.4' }}><strong>Recommendations:</strong> {report.strategic_recommendations}</p>
          </div>
        )}

        <h4 style={{ color: '#9ca3af', textTransform: 'uppercase', fontSize: '0.75rem', letterSpacing: '0.05em' }}>Ingested Database Records</h4>
        
        {projects.map((p) => (
          <div key={p.id} style={{ background: '#1f2937', padding: '12px', marginBottom: '10px', borderRadius: '6px', display: 'flex', gap: '12px', alignItems: 'flex-start', borderLeft: selectedIds.includes(p.id) ? '4px solid #3b82f6' : '4px solid transparent' }}>
            <input 
              type="checkbox" 
              checked={selectedIds.includes(p.id)}
              onChange={() => toggleSelect(p.id)}
              style={{ marginTop: '4px', cursor: 'pointer' }}
            />
            <div>
              <h4 style={{ margin: '0 0 4px 0', fontSize: '0.9rem' }}>{p.project_name}</h4>
              <p style={{ margin: '0 0 2px 0', fontSize: '0.8rem', color: '#9ca3af' }}>{p.utility_company} ({p.state})</p>
              <p style={{ margin: 0, fontSize: '0.75rem', color: '#6ee7b7' }}>In-Service: {p.in_service_date}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Map View */}
      <div style={{ flex: 1, height: '100%' }}>
        <MapContainer center={[32.74, -79.93]} zoom={6} style={{ height: '100%', width: '100%' }}>
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; OpenStreetMap contributors'
          />
          {projects.map((p) => (
            <Marker key={p.id} position={[p.latitude, p.longitude]}>
              <Popup>
                <div style={{ maxWidth: '220px' }}>
                  <strong>{p.project_name}</strong><br />
                  <p style={{ margin: '5px 0', fontSize: '0.85rem' }}>{p.project_scope}</p>
                  <em style={{ fontSize: '0.75rem' }}>Utility: {p.utility_company}</em>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}