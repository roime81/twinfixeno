"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import Keycloak from "keycloak-js";

type Patient = { id: number; external_id: string; given_name: string; family_name: string; birth_date: string; sex: string };
type Observation = { id: number; code: string; display: string; value: number; unit: string; observed_at: string };
type FhirStatus = { available: boolean; fhir_version?: string; software?: string; endpoint?: string; detail?: string };
type TimelineItem = { resource_type: string; resource_id: string; version_id?: string; title: string; status?: string; effective_at?: string; last_updated?: string; source?: string; resource?: Record<string, unknown> };
type Snapshot = { id: number; version: number; summary: string; created_at: string; content_sha256?: string; provenance?: Record<string, unknown> };
type SnapshotDetail = Snapshot & { integrity_verified: boolean; payload: Record<string, unknown>; provenance: Record<string, unknown> };
type AccessGrant = { id: number; patient_id: number; username?: string | null; user_subject?: string | null; access_level: "read" | "write" };
type RuntimeConfig = { apiBaseUrl: string; keycloakUrl: string; keycloakRealm: string; keycloakClientId: string };
type View = "overview" | "patients" | "timeline" | "snapshots" | "governance" | "integrations";

const DEFAULT_CONFIG: RuntimeConfig = {
  apiBaseUrl: "http://localhost:9080",
  keycloakUrl: "http://localhost:8081",
  keycloakRealm: "twinfixeno",
  keycloakClientId: "twinfixeno-web",
};
const NAV: { id: View; label: string; icon: string; adminOnly?: boolean }[] = [
  { id: "overview", label: "Overview", icon: "◈" },
  { id: "patients", label: "Patient registry", icon: "◎" },
  { id: "timeline", label: "Clinical timeline", icon: "⌁" },
  { id: "snapshots", label: "Twin snapshots", icon: "◇" },
  { id: "integrations", label: "FHIR integration", icon: "↗" },
  { id: "governance", label: "Access governance", icon: "▤", adminOnly: true },
];

function displayDate(value?: string) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
function shortHash(value?: string) {
  return value ? value.slice(0, 18) + "…" : "Not available";
}

export default function Home() {
  const keycloak = useRef<Keycloak | null>(null);
  const runtime = useRef<RuntimeConfig>(DEFAULT_CONFIG);
  const adminRole = useRef(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [username, setUsername] = useState("");
  const [roles, setRoles] = useState<string[]>([]);
  const [activeView, setActiveView] = useState<View>("overview");
  const [patients, setPatients] = useState<Patient[]>([]);
  const [patientId, setPatientId] = useState("");
  const [observations, setObservations] = useState<Observation[]>([]);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [snapshotDetail, setSnapshotDetail] = useState<SnapshotDetail | null>(null);
  const [grants, setGrants] = useState<AccessGrant[]>([]);
  const [fhirStatus, setFhirStatus] = useState<FhirStatus | null>(null);
  const [fhirMessage, setFhirMessage] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [loading, setLoading] = useState(true);
  const [grantUsername, setGrantUsername] = useState("");
  const [grantSubject, setGrantSubject] = useState("");
  const [grantLevel, setGrantLevel] = useState<"read" | "write">("read");
  const [selectedResource, setSelectedResource] = useState<TimelineItem | null>(null);

  const isAdmin = roles.includes("twinfixeno-admin");
  const canWrite = isAdmin || roles.includes("clinician");
  const patient = useMemo(
    () => patients.find((item) => String(item.id) === patientId) ?? null,
    [patients, patientId],
  );

  async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
    const client = keycloak.current;
    if (!client) throw new Error("Your session is not ready. Sign in again.");
    await client.updateToken(30);
    const headers = new Headers(init.headers);
    headers.set("Authorization", "Bearer " + client.token);
    if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const base = runtime.current.apiBaseUrl.replace(/\/$/, "");
    const response = await fetch(base + path, { ...init, headers });
    if (response.status === 204) return undefined as T;
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof body?.detail === "string" ? body.detail : "Request failed (" + response.status + ")";
      throw new Error(detail);
    }
    return body as T;
  }

  async function loadPatientData(id: string) {
    if (!id) return;
    const [obs, timelineResult, snapshotResult, status] = await Promise.all([
      api<Observation[]>("/api/v1/patients/" + id + "/observations"),
      api<{ items: TimelineItem[] }>("/api/v1/patients/" + id + "/timeline"),
      api<Snapshot[]>("/api/v1/patients/" + id + "/snapshots"),
      api<FhirStatus>("/api/v1/integrations/fhir/status"),
    ]);
    setObservations(obs);
    setTimeline(timelineResult.items ?? []);
    setSnapshots(snapshotResult);
    setFhirStatus(status);
    setSnapshotDetail(null);
    setSelectedResource(null);
    if (adminRole.current) {
      const access = await api<AccessGrant[]>("/api/v1/patients/" + id + "/access-grants");
      setGrants(access);
    } else {
      setGrants([]);
    }
  }

  async function refreshWorkspace() {
    setError("");
    setNotice("");
    setBusy("refresh");
    try {
      const result = await api<Patient[]>("/api/v1/patients");
      setPatients(result);
      if (result.length === 0) {
        setPatientId("");
        setObservations([]);
        setTimeline([]);
        setSnapshots([]);
        setNotice("Your account has no patient assignments. Ask an administrator to grant access.");
      } else {
        const nextId = result.some((item) => String(item.id) === patientId) ? patientId : String(result[0].id);
        setPatientId(nextId);
        await loadPatientData(nextId);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load the workspace.");
    } finally {
      setBusy("");
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    async function initialise() {
      try {
        const configResponse = await fetch("/runtime-config", { cache: "no-store" });
        if (!configResponse.ok) throw new Error("Unable to load application configuration.");
        const config = { ...DEFAULT_CONFIG, ...(await configResponse.json()) } as RuntimeConfig;
        if (!active) return;
        runtime.current = config;
        const client = new Keycloak({ url: config.keycloakUrl, realm: config.keycloakRealm, clientId: config.keycloakClientId });
        keycloak.current = client;
        const loggedIn = await client.init({ onLoad: "login-required", pkceMethod: "S256", checkLoginIframe: false });
        if (!active || !loggedIn) return;
        client.onTokenExpired = () => { client.updateToken(30).catch(() => client.login()); };
        const claims = client.tokenParsed as { preferred_username?: string; realm_access?: { roles?: string[] } };
        setUsername(claims?.preferred_username ?? "Signed in");
        const assignedRoles = claims?.realm_access?.roles ?? [];
        adminRole.current = assignedRoles.includes("twinfixeno-admin");
        setRoles(assignedRoles);
        setAuthenticated(true);
        await refreshWorkspace();
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Authentication or API connection failed.");
          setLoading(false);
        }
      }
    }
    void initialise();
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function choosePatient(id: string) {
    setPatientId(id);
    setError("");
    setNotice("");
    setBusy("patient");
    try { await loadPatientData(id); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to load this patient."); }
    finally { setBusy(""); }
  }

  async function syncFhir() {
    if (!patient) return;
    setBusy("fhir");
    setError("");
    setFhirMessage("Synchronising Patient and supported clinical resources…");
    try {
      const result = await api<{ patient_created: boolean; imported_count: number }>(
        "/api/v1/patients/" + patient.id + "/fhir/sync", { method: "POST" },
      );
      setFhirMessage("FHIR Patient " + (result.patient_created ? "created" : "matched") + " · " + result.imported_count + " Observation, Condition and Encounter resources synchronised.");
      await loadPatientData(String(patient.id));
    } catch (err) {
      const message = err instanceof Error ? err.message : "FHIR synchronisation failed.";
      setFhirMessage(message);
      setError(message);
    } finally { setBusy(""); }
  }

  async function createSnapshot() {
    if (!patient) return;
    setBusy("snapshot");
    setError("");
    try {
      const created = await api<Snapshot>("/api/v1/patients/" + patient.id + "/snapshots", { method: "POST" });
      await loadPatientData(String(patient.id));
      const detail = await api<SnapshotDetail>("/api/v1/patients/" + patient.id + "/snapshots/" + created.id);
      setSnapshotDetail(detail);
      setActiveView("snapshots");
      setNotice("Snapshot version " + created.version + " was created. Its SHA-256 digest was " + (detail.integrity_verified ? "verified." : "not verified."));
    } catch (err) { setError(err instanceof Error ? err.message : "Snapshot creation failed."); }
    finally { setBusy(""); }
  }

  async function openSnapshot(snapshotId: number) {
    if (!patient) return;
    setBusy("snapshot-" + snapshotId);
    setError("");
    try {
      const detail = await api<SnapshotDetail>("/api/v1/patients/" + patient.id + "/snapshots/" + snapshotId);
      setSnapshotDetail(detail);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to retrieve snapshot."); }
    finally { setBusy(""); }
  }

  async function saveGrant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!patient) return;
    setBusy("grant");
    setError("");
    setNotice("");
    try {
      await api<AccessGrant>("/api/v1/patients/" + patient.id + "/access-grants", {
        method: "POST",
        body: JSON.stringify({ username: grantUsername.trim() || null, user_subject: grantSubject.trim() || null, access_level: grantLevel }),
      });
      setGrantUsername("");
      setGrantSubject("");
      setNotice("Patient access grant saved.");
      await loadPatientData(String(patient.id));
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to save access grant."); }
    finally { setBusy(""); }
  }

  async function revokeGrant(grant: AccessGrant) {
    if (!patient) return;
    if (!window.confirm("Revoke " + (grant.username || grant.user_subject || "this user's") + " access to " + patient.external_id + "?")) return;
    setBusy("revoke-" + grant.id);
    setError("");
    try {
      await api<void>("/api/v1/patients/" + patient.id + "/access-grants/" + grant.id, { method: "DELETE" });
      setNotice("Access grant revoked.");
      await loadPatientData(String(patient.id));
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to revoke access grant."); }
    finally { setBusy(""); }
  }

  const headings: Record<View, { eyebrow: string; title: string; description: string }> = {
    overview: { eyebrow: "WORKSPACE / OVERVIEW", title: "Patient command centre", description: "A longitudinal view of the selected synthetic patient twin." },
    patients: { eyebrow: "WORKSPACE / PATIENTS", title: "Patient registry", description: "Browse only the patient records assigned to your identity." },
    timeline: { eyebrow: "CLINICAL DATA / TIMELINE", title: "Clinical timeline", description: "FHIR-backed Observation, Condition and Encounter resources." },
    snapshots: { eyebrow: "DIGITAL TWIN / SNAPSHOTS", title: "Twin snapshot library", description: "Immutable versions with content integrity and source provenance." },
    integrations: { eyebrow: "PLATFORM / INTEGRATIONS", title: "FHIR integration", description: "FHIR R4 connectivity, patient matching and resource synchronisation." },
    governance: { eyebrow: "PLATFORM / GOVERNANCE", title: "Access governance", description: "Administrator-managed patient-level access grants." },
  };
  const latest = (name: string) => observations.find((item) => item.display === name);
  const currentHeading = headings[activeView];

  if (!authenticated) {
    return (
      <div className="auth-screen"><div className="auth-card">
        <div className="brand">twinfixeno</div><div className="eyebrow">SECURE CLINICAL WORKSPACE</div>
        <h1>{error ? "Workspace unavailable" : "Connecting securely…"}</h1>
        <p>{error || "Connecting to Keycloak identity and loading your assigned workspace."}</p>
        {error && <div className="notice error-notice">{error}</div>}
        {error && <button className="primary-button" onClick={() => window.location.reload()}>Retry connection</button>}
      </div></div>
    );
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">twinfixeno</div><div className="subbrand">Healthcare Digital Twin</div>
        <div className="workspace-label">CLINICAL WORKSPACE</div>
        <nav className="nav" aria-label="Workspace navigation">
          {NAV.filter((item) => !item.adminOnly || isAdmin).map((item) => (
            <button className={"nav-item " + (activeView === item.id ? "active" : "")} key={item.id}
              onClick={() => { setActiveView(item.id); setError(""); }} type="button">
              <span className="nav-icon">{item.icon}</span><span>{item.label}</span>
              {item.id === "snapshots" && snapshots.length > 0 && <span className="nav-count">{snapshots.length}</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer"><span className="status-dot" />Synthetic data environment<div className="version">Workspace · 0.4.0</div></div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div><div className="eyebrow">{currentHeading.eyebrow}</div><h1 className="heading">{currentHeading.title}</h1><div className="muted">{currentHeading.description}</div></div>
          <div className="user-tools"><span className="user-pill"><span className="status-dot" />{username}</span>
            <button className="secondary-button" onClick={() => keycloak.current?.logout({ redirectUri: window.location.origin })}>Sign out</button>
          </div>
        </header>

        {error && <div className="notice error-notice" role="alert">{error}</div>}
        {notice && <div className="notice success-notice" role="status">{notice}</div>}
        <div className="toolbar">
          <label className="patient-picker"><span>ACTIVE PATIENT</span>
            <select aria-label="Active patient" value={patientId} onChange={(event) => void choosePatient(event.target.value)} disabled={patients.length === 0 || busy === "patient"}>
              {patients.length === 0 && <option value="">No patient assignments</option>}
              {patients.map((item) => <option value={item.id} key={item.id}>{item.external_id} · {item.given_name} {item.family_name}</option>)}
            </select>
          </label>
          <button className="secondary-button" onClick={() => void refreshWorkspace()} disabled={busy === "refresh"}>{busy === "refresh" ? "Refreshing…" : "↻ Refresh workspace"}</button>
        </div>

        {loading ? (
          <div className="card empty-state"><div className="spinner" /><strong>Loading your workspace</strong><span className="muted">Retrieving patient assignments and clinical data.</span></div>
        ) : !patient ? (
          <div className="card empty-state"><div className="empty-icon">◎</div><h2>No patient access</h2><p className="muted">Your identity is authenticated, but no patient record is assigned to this account.</p></div>
        ) : (
          <>
            {activeView === "overview" && <>
              <section className="metric-grid">
                <div className="metric-card"><div className="label">ASSIGNED PATIENTS</div><div className="metric">{String(patients.length).padStart(2, "0")}</div><div className="muted">Available to your account</div></div>
                <div className="metric-card"><div className="label">OBSERVATIONS</div><div className="metric">{String(observations.length).padStart(2, "0")}</div><div className="muted">Structured measurements</div></div>
                <div className="metric-card"><div className="label">TWIN SNAPSHOTS</div><div className="metric">{String(snapshots.length).padStart(2, "0")}</div><div className="muted">Immutable patient states</div></div>
                <div className="metric-card"><div className="label">FHIR R4 SERVER</div><div className={"metric status-metric " + (fhirStatus?.available ? "healthy" : "unhealthy")}>{fhirStatus ? (fhirStatus.available ? "Connected" : "Offline") : "Checking…"}</div><div className="muted">{fhirStatus?.fhir_version ? "FHIR " + fhirStatus.fhir_version : "HAPI FHIR endpoint"}</div></div>
              </section>
              <section className="section">
                <div className="section-heading"><div><h2>Patient digital twin</h2><p className="muted">Selected patient identity and current measurements.</p></div><span className="tag">SYNTHETIC RECORD</span></div>
                <div className="card patient-card">
                  <div className="patient-summary"><div className="avatar">{patient.given_name[0]}{patient.family_name[0]}</div>
                    <div><strong className="patient-name">{patient.given_name} {patient.family_name}</strong><div className="muted">{patient.external_id} · {patient.sex} · Born {patient.birth_date}</div></div>
                  </div>
                  <div className="action-stack">
                    <button className="secondary-button" onClick={() => setActiveView("patients")}>Patient record</button>
                    <button className="secondary-button" onClick={() => void syncFhir()} disabled={!canWrite || busy === "fhir"}>{busy === "fhir" ? "Syncing…" : "↗ Sync FHIR"}</button>
                    <button className="primary-button" onClick={() => void createSnapshot()} disabled={!canWrite || busy === "snapshot"}>{busy === "snapshot" ? "Creating…" : "＋ Create snapshot"}</button>
                  </div>
                  {fhirMessage && <div className="inline-message">{fhirMessage}</div>}
                  <div className="vitals-grid">
                    <div className="vital"><span>HEART RATE</span><strong>{latest("Heart rate")?.value ?? "—"} <small>bpm</small></strong></div>
                    <div className="vital"><span>BLOOD PRESSURE</span><strong>{latest("Systolic blood pressure")?.value ?? "—"} <small>/ {latest("Diastolic blood pressure")?.value ?? "—"} mmHg</small></strong></div>
                    <div className="vital"><span>BODY WEIGHT</span><strong>{latest("Body weight")?.value ?? "—"} <small>kg</small></strong></div>
                  </div>
                </div>
              </section>
              <section className="section">
                <div className="section-heading"><div><h2>Latest clinical observations</h2><p className="muted">Local synthetic measurements stored in the twin database.</p></div><button className="text-button" onClick={() => setActiveView("timeline")}>Open timeline →</button></div>
                <div className="card">
                  {observations.slice(0, 5).map((item) => <div className="data-row" key={item.id}><div><strong>{item.display}</strong><div className="muted">{displayDate(item.observed_at)}</div></div><strong className="row-value">{item.value} {item.unit}</strong></div>)}
                  {observations.length === 0 && <div className="empty-copy">No observations are available for this patient.</div>}
                </div>
              </section>
              <section className="section">
                <div className="section-heading"><div><h2>Recent twin snapshots</h2><p className="muted">Immutable capture history.</p></div><button className="text-button" onClick={() => setActiveView("snapshots")}>View all →</button></div>
                <div className="card">
                  {snapshots.slice(0, 3).map((item) => <div className="data-row" key={item.id}><div><strong>Snapshot v{item.version}</strong><div className="muted">{displayDate(item.created_at)}</div></div><button className="secondary-button compact" onClick={() => { setActiveView("snapshots"); void openSnapshot(item.id); }}>Inspect</button></div>)}
                  {snapshots.length === 0 && <div className="empty-copy">No snapshots created yet. A clinician or administrator can create the first version.</div>}
                </div>
              </section>
            </>}

            {activeView === "patients" && <section className="section">
              <div className="section-heading"><div><h2>Accessible patient records</h2><p className="muted">Patient visibility is enforced by the API for every request.</p></div><span className="tag">{patients.length} ASSIGNED</span></div>
              <div className="patient-list">
                {patients.map((item) => <button className={"patient-list-card " + (patientId === String(item.id) ? "selected" : "")} key={item.id} onClick={() => void choosePatient(String(item.id))}>
                  <div className="avatar">{item.given_name[0]}{item.family_name[0]}</div><div className="patient-list-info"><strong>{item.given_name} {item.family_name}</strong><span>{item.external_id} · {item.sex} · Born {item.birth_date}</span></div><span className="tag">{patientId === String(item.id) ? "SELECTED" : "OPEN RECORD"}</span>
                </button>)}
              </div>
              <div className="card patient-detail-card"><div className="section-heading"><h2>Selected patient profile</h2><span className="tag">SYNTHETIC</span></div>
                <div className="profile-grid">
                  <div><span>Patient ID</span><strong>{patient.external_id}</strong></div><div><span>Given name</span><strong>{patient.given_name}</strong></div>
                  <div><span>Family name</span><strong>{patient.family_name}</strong></div><div><span>Date of birth</span><strong>{patient.birth_date}</strong></div>
                  <div><span>Administrative sex</span><strong>{patient.sex}</strong></div><div><span>Local record key</span><strong>#{patient.id}</strong></div>
                </div>
              </div>
            </section>}

            {activeView === "timeline" && <section className="section">
              <div className="section-heading"><div><h2>FHIR clinical resources</h2><p className="muted">Imported from the configured FHIR R4 server and matched to this patient.</p></div><span className="tag">{timeline.length} RESOURCES</span></div>
              <div className="card">
                {timeline.length === 0 ? <div className="empty-state small"><div className="empty-icon">⌁</div><strong>No FHIR resources yet</strong><p className="muted">Run a FHIR sync from the integration page to populate this timeline.</p><button className="primary-button" onClick={() => setActiveView("integrations")} disabled={!canWrite}>Open FHIR integration</button></div> :
                  timeline.map((item, index) => <button className={"timeline-row " + (selectedResource === item ? "selected" : "")} key={item.resource_type + "-" + item.resource_id + "-" + index} onClick={() => setSelectedResource(selectedResource === item ? null : item)}>
                    <span className="timeline-marker" /><span className="timeline-content"><strong>{item.title}</strong><span>{item.resource_type} · {displayDate(item.effective_at)} · {item.status || "status unknown"}</span></span><span className="tag">{item.resource_type}</span><span className="muted">v{item.version_id || "—"}</span>
                  </button>)}
              </div>
              {selectedResource && <div className="card detail-card"><div className="section-heading"><div><h2>FHIR resource detail</h2><p className="muted">{selectedResource.resource_type}/{selectedResource.resource_id} · source {selectedResource.source || "unknown"}</p></div><button className="text-button" onClick={() => setSelectedResource(null)}>Close</button></div><pre className="json-view">{JSON.stringify(selectedResource.resource ?? selectedResource, null, 2)}</pre></div>}
            </section>}

            {activeView === "snapshots" && <section className="section">
              <div className="section-heading"><div><h2>Immutable twin history</h2><p className="muted">Each version captures local observations and imported FHIR resources.</p></div><button className="primary-button" onClick={() => void createSnapshot()} disabled={!canWrite || busy === "snapshot"}>{busy === "snapshot" ? "Creating…" : "＋ Create snapshot"}</button></div>
              <div className="snapshot-layout">
                <div className="card snapshot-list">
                  {snapshots.length === 0 ? <div className="empty-copy">No snapshots have been created for this patient.</div> :
                    snapshots.map((item) => <button className={"snapshot-item " + (snapshotDetail?.id === item.id ? "selected" : "")} key={item.id} onClick={() => void openSnapshot(item.id)}>
                      <div><strong>Version {item.version}</strong><span>{displayDate(item.created_at)}</span><code>{shortHash(item.content_sha256)}</code></div><span className="tag">{busy === "snapshot-" + item.id ? "LOADING" : "INSPECT"}</span>
                    </button>)}
                </div>
                <div className="card snapshot-inspector">
                  {!snapshotDetail ? <div className="empty-state small"><div className="empty-icon">◇</div><strong>Select a snapshot</strong><p className="muted">Inspect its integrity result, data payload and source provenance.</p></div> : <>
                    <div className="section-heading"><div><h2>Snapshot v{snapshotDetail.version}</h2><p className="muted">{displayDate(snapshotDetail.created_at)}</p></div><span className={"tag " + (snapshotDetail.integrity_verified ? "tag-good" : "tag-bad")}>{snapshotDetail.integrity_verified ? "HASH VERIFIED" : "HASH MISMATCH"}</span></div>
                    <div className="hash-block"><span>SHA-256 CONTENT DIGEST</span><code>{snapshotDetail.content_sha256}</code></div>
                    <div className="section-heading sub-heading"><h3>Source provenance</h3><span className="muted">{Array.isArray(snapshotDetail.provenance?.sources) ? snapshotDetail.provenance.sources.length : 0} sources</span></div>
                    <pre className="json-view">{JSON.stringify(snapshotDetail.provenance, null, 2)}</pre>
                    <div className="section-heading sub-heading"><h3>Captured twin payload</h3></div><pre className="json-view">{JSON.stringify(snapshotDetail.payload, null, 2)}</pre>
                  </>}
                </div>
              </div>
            </section>}

            {activeView === "integrations" && <section className="section">
              <div className="section-heading"><div><h2>FHIR R4 connectivity</h2><p className="muted">FHIR capability statement and patient-scoped synchronisation.</p></div><span className={"tag " + (fhirStatus?.available ? "tag-good" : "tag-bad")}>{fhirStatus?.available ? "ONLINE" : "UNAVAILABLE"}</span></div>
              <div className="card integration-card"><div className="integration-symbol">FHIR</div>
                <div className="integration-copy"><h2>{fhirStatus?.software || "HAPI FHIR server"}</h2><p className="muted">{fhirStatus?.available ? "FHIR version " + (fhirStatus.fhir_version || "R4") : "The server did not return a valid capability statement."}</p><code>{fhirStatus?.endpoint || "FHIR endpoint configured inside API service"}</code></div>
                <button className="primary-button" onClick={() => void syncFhir()} disabled={!canWrite || busy === "fhir" || !fhirStatus?.available}>{busy === "fhir" ? "Synchronising…" : "↻ Synchronise patient"}</button>
              </div>
              {fhirMessage && <div className="notice">{fhirMessage}</div>}
              <div className="section-heading section-spaced"><div><h2>Supported resource ingestion</h2><p className="muted">Resources are checked against the resolved Patient reference before persistence.</p></div></div>
              <div className="resource-grid">{["Patient", "Observation", "Condition", "Encounter"].map((name) => <div className="resource-card" key={name}><span className="resource-check">✓</span><strong>{name}</strong><span className="muted">{name === "Patient" ? "Identifier-based match" : "Patient-scoped import"}</span></div>)}</div>
              <div className="notice">FHIR synchronisation is enabled for clinician and administrator roles with write access to this patient. Researcher accounts remain read-only.</div>
            </section>}

            {activeView === "governance" && <section className="section">
              {isAdmin ? <>
                <div className="section-heading"><div><h2>Patient access grants</h2><p className="muted">Grant read or write access to a Keycloak user for the selected patient.</p></div><span className="tag">ADMINISTRATOR</span></div>
                <div className="card grant-card"><h3>Create or update a grant</h3>
                  <form className="grant-form" onSubmit={(event) => void saveGrant(event)}>
                    <label>Keycloak username<input value={grantUsername} onChange={(event) => setGrantUsername(event.target.value)} placeholder="e.g. clinician.jane" /></label>
                    <div className="form-divider">OR</div>
                    <label>Keycloak subject (sub)<input value={grantSubject} onChange={(event) => setGrantSubject(event.target.value)} placeholder="OIDC subject UUID" /></label>
                    <label>Permission<select value={grantLevel} onChange={(event) => setGrantLevel(event.target.value as "read" | "write")}><option value="read">Read only</option><option value="write">Read and write</option></select></label>
                    <button className="primary-button" type="submit" disabled={busy === "grant" || (!grantUsername.trim() && !grantSubject.trim())}>{busy === "grant" ? "Saving…" : "Save access grant"}</button>
                  </form>
                  <p className="muted form-help">Provide a username or subject identifier. Existing matching grants are updated; revocation takes effect immediately.</p>
                </div>
                <div className="card grant-table-card"><div className="section-heading"><div><h2>Current grants</h2><p className="muted">{grants.length} principal assignments for {patient.external_id}</p></div></div>
                  {grants.length === 0 ? <div className="empty-copy">No explicit patient grants exist. Administrators retain platform-wide access.</div> :
                    <div className="table-scroll"><table className="grant-table"><thead><tr><th>Username</th><th>Subject</th><th>Permission</th><th>Action</th></tr></thead><tbody>
                      {grants.map((grant) => <tr key={grant.id}><td>{grant.username || "—"}</td><td><code>{grant.user_subject || "—"}</code></td><td><span className={"tag " + (grant.access_level === "write" ? "tag-good" : "")}>{grant.access_level.toUpperCase()}</span></td><td><button className="danger-button" onClick={() => void revokeGrant(grant)} disabled={busy === "revoke-" + grant.id}>{busy === "revoke-" + grant.id ? "Revoking…" : "Revoke"}</button></td></tr>)}
                    </tbody></table></div>}
                </div>
              </> : <div className="card empty-state"><div className="empty-icon">▤</div><h2>Administrator access required</h2><p className="muted">Only users with the twinfixeno-admin role can view or change patient access grants.</p></div>}
            </section>}
          </>
        )}
        <footer className="page-footer"><span>twinfixeno · Synthetic data environment</span><span>Not a medical device · Not for diagnosis or treatment</span></footer>
      </main>
    </div>
  );
}
