"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import Keycloak from "keycloak-js";

type Patient = { id: number; external_id: string; given_name: string; family_name: string; birth_date: string; sex: string };
type Observation = { id: number; code: string; display: string; value: number; unit: string; observed_at: string };
type FhirStatus = { available: boolean; fhir_version?: string; software?: string; detail?: string };
type TimelineItem = { resource_type: string; resource_id: string; version_id?: string; title: string; status?: string; effective_at?: string; last_updated?: string; source?: string };
type Snapshot = { id: number; version: number; summary: string; created_at: string; content_sha256?: string };
type Grant = { id: number; username?: string; user_subject?: string; access_level: "read" | "write" };
type AuditEvent = { id: number; actor_username?: string; action: string; patient_id?: number; resource_type?: string; resource_id?: string; created_at: string };
type Simulation = { id: number; scenario_name: string; formula_id: string; inputs: Record<string, unknown>; result: { baseline_value: number; projected_value: number; absolute_delta: number; unit: string; label: string; assumptions: string[] }; created_at: string };
type Permissions = { can_read: boolean; can_write: boolean; can_manage_access: boolean };
type View = "overview" | "registry" | "timeline" | "simulation" | "copilot" | "snapshots" | "governance";

const VIEWS: { id: View; label: string; icon: string }[] = [
  { id: "overview", label: "Command centre", icon: "◈" },
  { id: "registry", label: "Patient registry", icon: "◎" },
  { id: "timeline", label: "Clinical timeline", icon: "⌁" },
  { id: "simulation", label: "Simulation studio", icon: "◇" },
  { id: "copilot", label: "Evidence assistant", icon: "✳" },
  { id: "snapshots", label: "Twin snapshots", icon: "▤" },
  { id: "governance", label: "Governance & audit", icon: "⚑" },
];

function formatDate(value?: string) {
  if (!value) return "Not recorded";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function displayPatient(patient?: Patient | null) {
  return patient ? patient.given_name + " " + patient.family_name : "No patient selected";
}

export default function Home() {
  const keycloak = useRef<Keycloak | null>(null);
  const patientLoadSequence = useRef(0);
  const runtime = useRef({ apiBaseUrl: "http://localhost:9080", keycloakUrl: "http://localhost:8081", keycloakRealm: "twinfixeno", keycloakClientId: "twinfixeno-web" });
  const [authenticated, setAuthenticated] = useState(false);
  const [username, setUsername] = useState("");
  const [roles, setRoles] = useState<string[]>([]);
  const [view, setView] = useState<View>("overview");
  const [patients, setPatients] = useState<Patient[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState<number | null>(null);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [simulations, setSimulations] = useState<Simulation[]>([]);
  const [permissions, setPermissions] = useState<Permissions>({ can_read: false, can_write: false, can_manage_access: false });
  const [fhirStatus, setFhirStatus] = useState<FhirStatus | null>(null);
  const [grants, setGrants] = useState<Grant[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [contextReport, setContextReport] = useState<any>(null);
  const [ragQuestion, setRagQuestion] = useState("");
  const [ragAnswer, setRagAnswer] = useState<any>(null);
  const [ragStatus, setRagStatus] = useState<any>(null);
  const [selectedSnapshot, setSelectedSnapshot] = useState<any>(null);
  const [registrySearch, setRegistrySearch] = useState("");
  const [scenarioName, setScenarioName] = useState("Illustrative scenario");
  const [baselineObservationId, setBaselineObservationId] = useState("");
  const [changePercent, setChangePercent] = useState(10);
  const [grantUsername, setGrantUsername] = useState("");
  const [grantSubject, setGrantSubject] = useState("");
  const [grantLevel, setGrantLevel] = useState<"read" | "write">("read");
  const [newPatient, setNewPatient] = useState({ external_id: "SYN-0002", given_name: "", family_name: "", birth_date: "1980-01-01", sex: "unknown" });
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const patient = useMemo(() => patients.find(item => item.id === selectedPatientId) || null, [patients, selectedPatientId]);
  const canAdmin = roles.includes("twinfixeno-admin");

  async function api<T = any>(path: string, init: RequestInit = {}): Promise<T> {
    const client = keycloak.current;
    if (!client?.token) throw new Error("Your login session has expired. Sign in again.");
    await client.updateToken(30);
    const headers = new Headers(init.headers || {});
    headers.set("Authorization", "Bearer " + client.token);
    if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const response = await fetch(runtime.current.apiBaseUrl.replace(/\/$/, "") + path, { ...init, headers });
    const raw = await response.text();
    let data: any = null;
    try { data = raw ? JSON.parse(raw) : null; } catch { data = raw; }
    if (!response.ok) {
      const detail = data && typeof data === "object" && data.detail ? data.detail : response.statusText;
      throw new Error(String(detail || "Request failed") + " (" + response.status + ")");
    }
    return data as T;
  }

  async function loadPatient(patientId: number) {
    const sequence = ++patientLoadSequence.current;
    setLoading(true);
    setError("");
    // Clear patient-scoped state before switching context. Never leave the prior
    // patient's records or AI answer visible while the next patient is loading.
    setObservations([]);
    setTimeline([]);
    setSnapshots([]);
    setSimulations([]);
    setPermissions({ can_read: false, can_write: false, can_manage_access: false });
    setSelectedSnapshot(null);
    setContextReport(null);
    setRagAnswer(null);
    setRagQuestion("");
    setGrants([]);
    setAuditEvents([]);
    setRagStatus(null);
    try {
      const [patientData, obs, events, snapshotItems, simItems, perms] = await Promise.all([
        api<Patient>("/api/v1/patients/" + patientId),
        api<Observation[]>("/api/v1/patients/" + patientId + "/observations"),
        api<any>("/api/v1/patients/" + patientId + "/timeline"),
        api<Snapshot[]>("/api/v1/patients/" + patientId + "/snapshots"),
        api<Simulation[]>("/api/v1/patients/" + patientId + "/simulations"),
        api<Permissions>("/api/v1/patients/" + patientId + "/permissions"),
      ]);
      // Ignore late responses from an earlier selection.
      if (sequence !== patientLoadSequence.current) return;
      setPatients(current => current.map(item => item.id === patientData.id ? patientData : item));
      setObservations(obs);
      setTimeline(events.items || []);
      setSnapshots(snapshotItems);
      setSimulations(simItems);
      setPermissions(perms);
      setBaselineObservationId(obs[0] ? String(obs[0].id) : "");
      setContextReport(null);
      setSelectedSnapshot(null);
    } catch (err: any) {
      if (sequence === patientLoadSequence.current) {
        setError(err?.message || "Unable to load the selected patient.");
      }
    } finally {
      if (sequence === patientLoadSequence.current) setLoading(false);
    }
  }

  async function loadGovernance(patientId: number) {
    try {
      const [grantItems, events] = await Promise.all([
        api<Grant[]>("/api/v1/patients/" + patientId + "/access-grants"),
        api<AuditEvent[]>("/api/v1/audit/events?limit=100"),
      ]);
      setGrants(grantItems);
      setAuditEvents(events);
    } catch (err: any) {
      setError(err?.message || "Unable to load governance information.");
    }
  }

  useEffect(() => {
    let alive = true;
    async function initialise() {
      try {
        const response = await fetch("/runtime-config", { cache: "no-store" });
        if (!response.ok) throw new Error("Unable to load runtime configuration.");
        const config = await response.json();
        if (!alive) return;
        runtime.current = {
          apiBaseUrl: config.apiBaseUrl || "http://localhost:9080",
          keycloakUrl: config.keycloakUrl || "http://localhost:8081",
          keycloakRealm: config.keycloakRealm || "twinfixeno",
          keycloakClientId: config.keycloakClientId || "twinfixeno-web",
        };
        const client = new Keycloak({
          url: runtime.current.keycloakUrl,
          realm: runtime.current.keycloakRealm,
          clientId: runtime.current.keycloakClientId,
        });
        keycloak.current = client;
        const authenticatedNow = await client.init({
          onLoad: "login-required",
          pkceMethod: "S256",
          checkLoginIframe: false,
        });
        if (!alive) return;
        if (!authenticatedNow) {
          setError("Sign in was not completed. Reload the page to try again.");
          setLoading(false);
          return;
        }
        setAuthenticated(true);
        setUsername(String(client.tokenParsed?.preferred_username || "Signed in"));
        const tokenRoles = (client.tokenParsed as any)?.realm_access?.roles || [];
        setRoles(tokenRoles);
        client.onTokenExpired = () => { client.updateToken(30).catch(() => client.login()); };
        const [patientItems, fhir] = await Promise.all([
          api<Patient[]>("/api/v1/patients"),
          api<FhirStatus>("/api/v1/integrations/fhir/status"),
        ]);
        if (!alive) return;
        setPatients(patientItems);
        setFhirStatus(fhir);
        if (patientItems.length) {
          setSelectedPatientId(patientItems[0].id);
          await loadPatient(patientItems[0].id);
        } else {
          setLoading(false);
        }
      } catch (err: any) {
        if (alive) {
          setError(err?.message || "Authentication or API connection failed.");
          setLoading(false);
        }
      }
    }
    void initialise();
    return () => { alive = false; };
    // Authentication is deliberately initialised once per browser session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (authenticated && view === "governance" && selectedPatientId && canAdmin) {
      void loadGovernance(selectedPatientId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authenticated, view, selectedPatientId, canAdmin]);

  useEffect(() => {
    if (!authenticated || view !== "copilot") return;
    let active = true;
    setRagStatus(null);
    api<any>("/api/v1/ai/status")
      .then(status => { if (active) setRagStatus(status); })
      .catch((err: any) => {
        if (active) {
          setRagStatus({ ready: false, detail: err?.message || "Unable to reach local AI services." });
        }
      });
    return () => { active = false; };
    // API client is stable for the lifetime of this authenticated page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authenticated, view]);

  async function selectPatient(id: number) {
    setSelectedPatientId(id);
    await loadPatient(id);
    setView("overview");
  }

  async function syncFhir() {
    if (!patient || !permissions.can_write) return;
    setBusy(true); setNotice(""); setError("");
    try {
      const result = await api<any>("/api/v1/patients/" + patient.id + "/fhir/sync", { method: "POST" });
      setNotice("FHIR sync completed. " + result.published_observation_count + " local observations published; " + result.imported_count + " resources imported.");
      const status = await api<FhirStatus>("/api/v1/integrations/fhir/status");
      setFhirStatus(status);
      await loadPatient(patient.id);
    } catch (err: any) { setError(err?.message || "FHIR sync failed."); }
    finally { setBusy(false); }
  }

  async function createSnapshot() {
    if (!patient || !permissions.can_write) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await api<any>("/api/v1/patients/" + patient.id + "/snapshots", { method: "POST" });
      setNotice("Snapshot v" + result.version + " created. SHA-256: " + result.content_sha256);
      const items = await api<Snapshot[]>("/api/v1/patients/" + patient.id + "/snapshots");
      setSnapshots(items);
    } catch (err: any) { setError(err?.message || "Snapshot creation failed."); }
    finally { setBusy(false); }
  }

  async function openSnapshot(item: Snapshot) {
    if (!patient) return;
    setBusy(true); setError("");
    try {
      const detail = await api<any>("/api/v1/patients/" + patient.id + "/snapshots/" + item.id);
      setSelectedSnapshot(detail);
    } catch (err: any) { setError(err?.message || "Unable to load snapshot."); }
    finally { setBusy(false); }
  }

  async function createSimulation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!patient || !permissions.can_write || !baselineObservationId) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await api<Simulation>("/api/v1/patients/" + patient.id + "/simulations", {
        method: "POST",
        body: JSON.stringify({ scenario_name: scenarioName, baseline_observation_id: Number(baselineObservationId), change_percent: Number(changePercent) }),
      });
      setSimulations(current => [result, ...current]);
      setNotice("Hypothetical scenario saved as run #" + result.id + ".");
    } catch (err: any) { setError(err?.message || "Simulation failed."); }
    finally { setBusy(false); }
  }

  async function createPatient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      const created = await api<Patient>("/api/v1/patients", { method: "POST", body: JSON.stringify(newPatient) });
      const updated = await api<Patient[]>("/api/v1/patients");
      setPatients(updated);
      setNotice("Synthetic patient " + created.external_id + " created.");
      setNewPatient(current => ({ ...current, external_id: "SYN-" + String(Number(current.external_id.replace("SYN-", "")) + 1).padStart(4, "0"), given_name: "", family_name: "" }));
      await selectPatient(created.id);
    } catch (err: any) { setError(err?.message || "Patient creation failed."); }
    finally { setBusy(false); }
  }

  async function saveGrant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!patient) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await api("/api/v1/patients/" + patient.id + "/access-grants", {
        method: "POST",
        body: JSON.stringify({ username: grantUsername || null, user_subject: grantSubject || null, access_level: grantLevel }),
      });
      setGrantUsername(""); setGrantSubject("");
      await loadGovernance(patient.id);
      setNotice("Patient access grant saved.");
    } catch (err: any) { setError(err?.message || "Unable to save access grant."); }
    finally { setBusy(false); }
  }

  async function revokeGrant(grantId: number) {
    if (!patient) return;
    setBusy(true); setError("");
    try {
      await api("/api/v1/patients/" + patient.id + "/access-grants/" + grantId, { method: "DELETE" });
      await loadGovernance(patient.id);
      setNotice("Access grant revoked.");
    } catch (err: any) { setError(err?.message || "Unable to revoke access grant."); }
    finally { setBusy(false); }
  }

  async function generateContext() {
    if (!patient) return;
    setBusy(true); setError("");
    try {
      const report = await api<any>("/api/v1/patients/" + patient.id + "/insights");
      setContextReport(report);
    } catch (err: any) { setError(err?.message || "Unable to create local context report."); }
    finally { setBusy(false); }
  }

  const filteredPatients = patients.filter(item => {
    const query = registrySearch.trim().toLowerCase();
    return !query || [item.external_id, item.given_name, item.family_name].some(value => value.toLowerCase().includes(query));
  });
  const latest = (name: string) => observations.find(item => item.display === name);
  const vitalCards = [
    { label: "Heart rate", value: latest("Heart rate") },
    { label: "Blood pressure", value: latest("Systolic blood pressure"), suffix: " / " + (latest("Diastolic blood pressure")?.value ?? "—") + " mmHg" },
    { label: "Body weight", value: latest("Body weight") },
    { label: "Body temperature", value: latest("Body temperature") },
  ];
  const selectedBaseline = observations.find(item => item.id === Number(baselineObservationId));
  const projectedValue = selectedBaseline ? Number((selectedBaseline.value * (1 + changePercent / 100)).toFixed(3)) : null;

  if (!authenticated) {
    return <div className="auth-screen"><div className="auth-card"><div className="brand">twinfixeno</div><h1>Secure clinical workspace</h1><p>Connecting to the identity service…</p>{error && <div className="notice error">{error}</div>}</div></div>;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">twinfixeno</div>
        <div className="subbrand">Healthcare Digital Twin</div>
        <div className="env-chip"><span className="status-dot" /> Synthetic data workspace</div>
        <nav className="nav-list" aria-label="Main navigation">
          {VIEWS.map(item => (
            <button key={item.id} className={view === item.id ? "nav-item active" : "nav-item"} onClick={() => setView(item.id)}>
              <span className="nav-icon">{item.icon}</span><span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer"><strong>MVP 0.4.0</strong><span>FHIR R4 · OIDC · Audit</span><span>Research / demonstration only</span></div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="topbar-context"><span className="eyebrow">WORKSPACE / {view.toUpperCase()}</span><h1>{VIEWS.find(item => item.id === view)?.label}</h1><p>{patient ? displayPatient(patient) + " · " + patient.external_id : "No patient selected"}</p></div>
          <div className="topbar-actions">
            {patients.length > 0 && <label className="patient-switch"><span>ACTIVE TWIN</span><select value={selectedPatientId ?? ""} onChange={event => void selectPatient(Number(event.target.value))}>{patients.map(item => <option value={item.id} key={item.id}>{item.external_id} · {displayPatient(item)}</option>)}</select></label>}
            <div className="user-chip"><span className="user-avatar">{username.slice(0, 1).toUpperCase()}</span><span>{username}</span></div>
            <button className="button button-quiet" onClick={() => keycloak.current?.logout({ redirectUri: window.location.origin })}>Sign out</button>
          </div>
        </header>

        {error && <div className="notice error" role="alert">{error}<button onClick={() => setError("")} aria-label="Dismiss">×</button></div>}
        {notice && <div className="notice success" role="status">{notice}<button onClick={() => setNotice("")} aria-label="Dismiss">×</button></div>}
        {loading && <div className="loading-line"><span /> Loading authorised patient data…</div>}

        {!loading && patients.length === 0 && (
          <section className="panel empty-state"><div className="empty-icon">◎</div><h2>No patient records are assigned to this account</h2><p>Ask a platform administrator to grant access to a synthetic patient. Administrators can create demo patients in the registry.</p>{canAdmin && <button className="button" onClick={() => setView("registry")}>Open patient registry</button>}</section>
        )}

        {patient && view === "overview" && (
          <>
            <section className="welcome-row"><div><div className="eyebrow">PATIENT DIGITAL TWIN</div><h2>{displayPatient(patient)}</h2><p>{patient.external_id} · {patient.sex} · Date of birth {patient.birth_date}</p></div><div className="action-row"><button className="button button-secondary" disabled={!permissions.can_write || busy} onClick={() => void syncFhir()}>↗ Sync FHIR</button><button className="button" disabled={!permissions.can_write || busy} onClick={() => void createSnapshot()}>＋ Create snapshot</button></div></section>
            <section className="stat-grid">
              <div className="stat-card"><span>AUTHORISED PATIENTS</span><strong>{patients.length.toString().padStart(2, "0")}</strong><small>Visible to your account</small></div>
              <div className="stat-card"><span>OBSERVATIONS</span><strong>{observations.length.toString().padStart(2, "0")}</strong><small>Structured measurements</small></div>
              <div className="stat-card"><span>TWIN SNAPSHOTS</span><strong>{snapshots.length.toString().padStart(2, "0")}</strong><small>Immutable versions</small></div>
              <div className="stat-card"><span>FHIR R4</span><strong className={fhirStatus?.available ? "status-good" : "status-bad"}>{fhirStatus?.available ? "Online" : "Offline"}</strong><small>{fhirStatus?.fhir_version ? "FHIR " + fhirStatus.fhir_version : "HAPI FHIR endpoint"}</small></div>
            </section>
            <section className="content-grid">
              <div className="panel panel-wide"><div className="panel-heading"><div><span className="eyebrow">LATEST MEASUREMENTS</span><h3>Patient observations</h3></div><button className="text-button" onClick={() => setView("timeline")}>Open timeline →</button></div>
                <div className="vital-grid">{vitalCards.map(card => <div className="vital-card" key={card.label}><span>{card.label}</span><strong>{card.value ? card.value.value : "—"}<small>{card.suffix || (card.value ? " " + card.value.unit : "")}</small></strong><em>{card.value ? formatDate(card.value.observed_at) : "No data"}</em></div>)}</div>
                <div className="table-wrap"><table><thead><tr><th>Observation</th><th>Value</th><th>Recorded</th></tr></thead><tbody>{observations.slice(0, 6).map(item => <tr key={item.id}><td><strong>{item.display}</strong><small>{item.code}</small></td><td>{item.value} {item.unit}</td><td>{formatDate(item.observed_at)}</td></tr>)}</tbody></table></div>
              </div>
              <div className="panel"><div className="panel-heading"><div><span className="eyebrow">INTEGRATION HEALTH</span><h3>FHIR connection</h3></div><span className={fhirStatus?.available ? "state-pill good" : "state-pill bad"}>{fhirStatus?.available ? "Connected" : "Unavailable"}</span></div>
                <p className="panel-copy">{fhirStatus?.software || "HAPI FHIR"} · {fhirStatus?.fhir_version || "FHIR R4"}</p><div className="info-row"><span>Clinical resources</span><strong>{timeline.length}</strong></div><div className="info-row"><span>Published observations</span><strong>{observations.length}</strong></div><div className="info-row"><span>Latest sync status</span><strong>{fhirStatus?.available ? "Ready" : "Check service"}</strong></div><button className="button button-full" disabled={!permissions.can_write || busy || !fhirStatus?.available} onClick={() => void syncFhir()}>Synchronise patient data</button>
              </div>
            </section>
            <section className="panel"><div className="panel-heading"><div><span className="eyebrow">TWIN STATE</span><h3>Snapshot history</h3></div><button className="text-button" onClick={() => setView("snapshots")}>View all →</button></div>
              {snapshots.length === 0 ? <p className="muted">No snapshots yet. Create a snapshot to capture the current patient state and provenance.</p> : snapshots.slice(0, 3).map(item => <div className="list-row" key={item.id}><div><strong>Snapshot v{item.version}</strong><small>{formatDate(item.created_at)} · {item.summary}</small></div><button className="button button-quiet" onClick={() => void openSnapshot(item)}>Inspect</button></div>)}
            </section>
          </>
        )}

        {!loading && view === "registry" && (
          <section className="panel">
            <div className="panel-heading"><div><span className="eyebrow">PATIENT MANAGEMENT</span><h3>Authorised patient registry</h3><p className="panel-copy">Only synthetic patients granted to your identity are listed.</p></div><span className="state-pill">{patients.length} record(s)</span></div>
            <input className="search-input" value={registrySearch} onChange={event => setRegistrySearch(event.target.value)} placeholder="Search patient ID, given name or family name…" />
            <div className="table-wrap"><table><thead><tr><th>Patient</th><th>Identifier</th><th>Date of birth</th><th>Sex</th><th>Access</th><th /></tr></thead><tbody>
              {filteredPatients.map(item => <tr key={item.id}><td><strong>{displayPatient(item)}</strong></td><td>{item.external_id}</td><td>{item.birth_date}</td><td>{item.sex}</td><td><span className="state-pill">{item.id === selectedPatientId ? (permissions.can_write ? "Read / write" : "Read only") : "Granted"}</span></td><td><button className="text-button" onClick={() => void selectPatient(item.id)}>Open twin →</button></td></tr>)}
              {filteredPatients.length === 0 && <tr><td colSpan={6}>No matching patient records.</td></tr>}
            </tbody></table></div>
            {canAdmin && <div className="subpanel"><h4>Create synthetic patient</h4><form className="form-grid" onSubmit={createPatient}>
              <label>Patient ID<input required value={newPatient.external_id} onChange={event => setNewPatient({ ...newPatient, external_id: event.target.value })} /></label>
              <label>Given name<input required value={newPatient.given_name} onChange={event => setNewPatient({ ...newPatient, given_name: event.target.value })} /></label>
              <label>Family name<input required value={newPatient.family_name} onChange={event => setNewPatient({ ...newPatient, family_name: event.target.value })} /></label>
              <label>Date of birth<input required type="date" value={newPatient.birth_date} onChange={event => setNewPatient({ ...newPatient, birth_date: event.target.value })} /></label>
              <label>Sex<select value={newPatient.sex} onChange={event => setNewPatient({ ...newPatient, sex: event.target.value })}><option value="unknown">Unknown</option><option value="female">Female</option><option value="male">Male</option></select></label>
              <button className="button" disabled={busy}>Create synthetic patient</button>
            </form></div>}
          </section>
        )}

        {!loading && patient && view === "timeline" && (
          <section className="panel">
            <div className="panel-heading"><div><span className="eyebrow">LONGITUDINAL RECORD</span><h3>Clinical timeline</h3><p className="panel-copy">FHIR resources ordered by effective time. Source resource IDs and versions are retained.</p></div><button className="button button-secondary" disabled={!permissions.can_write || busy || !fhirStatus?.available} onClick={() => void syncFhir()}>Sync from FHIR</button></div>
            {timeline.length === 0 ? <div className="empty-inline"><strong>No FHIR clinical resources imported yet.</strong><p>Use Sync from FHIR to publish the local demo observations and import available Observation, Condition and Encounter resources.</p></div> :
              <div className="timeline-list">{timeline.map((item, index) => <div className="timeline-entry" key={item.resource_type + item.resource_id + index}><div className="timeline-marker" /><div className="timeline-body"><div className="timeline-title"><strong>{item.title}</strong><span className="type-pill">{item.resource_type}</span><span className="muted">v{item.version_id || "—"}</span></div><p>{formatDate(item.effective_at || item.last_updated)} · {item.status || "Status not supplied"}</p><small>FHIR ID: {item.resource_id} · Source: {item.source || "HAPI FHIR"}</small></div></div>)}</div>}
          </section>
        )}

        {!loading && patient && view === "simulation" && (
          <section className="panel">
            <div className="panel-heading"><div><span className="eyebrow">DETERMINISTIC ENGINE · PERCENTAGE-DELTA-V1</span><h3>Simulation studio</h3><p className="panel-copy">Create a saved, reproducible arithmetic scenario against one observed value.</p></div><span className="state-pill warning">Hypothetical only</span></div>
            <div className="simulation-layout"><form className="simulation-form" onSubmit={createSimulation}>
              <label>Scenario name<input required minLength={3} maxLength={120} value={scenarioName} onChange={event => setScenarioName(event.target.value)} /></label>
              <label>Baseline observation<select required value={baselineObservationId} onChange={event => setBaselineObservationId(event.target.value)}>{observations.map(item => <option key={item.id} value={item.id}>{item.display} · {item.value} {item.unit}</option>)}</select></label>
              <label>Hypothetical change <strong>{changePercent > 0 ? "+" : ""}{changePercent}%</strong><input type="range" min={-50} max={50} step={1} value={changePercent} onChange={event => setChangePercent(Number(event.target.value))} /></label>
              <p className="muted">A bounded arithmetic adjustment (−50% to +50%). It does not model physiology, treatment, interactions or causal effects.</p>
              <button className="button" disabled={!permissions.can_write || busy || !observations.length}>Save scenario run</button>
              {!permissions.can_write && <small className="muted">Your account has read-only access to this patient.</small>}
            </form>
              <div className="scenario-preview"><span className="eyebrow">LIVE SCENARIO PREVIEW</span><div className="scenario-values"><div><small>BASELINE</small><strong>{selectedBaseline ? selectedBaseline.value : "—"}</strong><em>{selectedBaseline?.unit || ""}</em></div><span>→</span><div><small>PROJECTED VALUE</small><strong>{projectedValue ?? "—"}</strong><em>{selectedBaseline?.unit || ""}</em></div></div><div className="scenario-delta">{changePercent > 0 ? "+" : ""}{changePercent}% applied to selected baseline</div><div className="warning-block">HYPOTHETICAL SCENARIO — NOT A CLINICAL PREDICTION</div><small>Formula: projected = baseline × (1 + change / 100)</small></div>
            </div>
            <div className="panel-heading history-heading"><div><span className="eyebrow">PERSISTED RUNS</span><h3>Scenario history</h3></div></div>
            {simulations.length === 0 ? <p className="muted">No scenario runs have been saved.</p> : simulations.map(item => <div className="list-row" key={item.id}><div><strong>{item.scenario_name}</strong><small>{formatDate(item.created_at)} · {item.result.baseline_value} → {item.result.projected_value} {item.result.unit}</small></div><span className="type-pill">{item.formula_id}</span></div>)}
          </section>
        )}

        {!loading && patient && view === "copilot" && (
          <section className="panel">
            <div className="panel-heading"><div><span className="eyebrow">LOCAL OPEN-SOURCE AI</span><h3>Evidence assistant</h3><p className="panel-copy">Ollama LLM + embeddings + patient-scoped Qdrant retrieval. No external AI API.</p></div><span className={ragStatus?.ready ? "state-pill good" : ragStatus ? "state-pill bad" : "state-pill"}>{ragStatus?.ready ? "AI ready" : ragStatus ? "AI unavailable" : "Checking AI services"}</span></div>
            <div className="assistant-banner"><div className="assistant-icon">✳</div><div><strong>Private, evidence-grounded RAG</strong><p>Index the selected patient's records, then ask questions. Answers include retrieved source evidence. Synthetic data only; not clinical decision support.</p>{ragStatus && <small>{ragStatus.ready ? "Models and vector store are connected." : (ragStatus.detail || ragStatus.ollama_error || ragStatus.qdrant_error || "The local model or vector store is not ready. Check Docker logs and model download status.")}</small>}</div></div>
            <button className="button button-secondary" disabled={busy} onClick={async () => { try { setRagStatus(await api<any>("/api/v1/ai/status")); } catch (e:any) { setError(e.message); } }}>Check local AI status</button>
            <button className="button" disabled={busy || !permissions.can_write || !ragStatus?.ready} onClick={async () => { setBusy(true); setError(""); try { const result=await api<any>("/api/v1/patients/"+patient.id+"/rag/index",{method:"POST"}); setNotice("Indexed "+result.indexed+" patient evidence records using "+result.embedding_model+"."); setRagStatus(await api<any>("/api/v1/ai/status")); } catch(e:any) { setError(e.message); } finally { setBusy(false); } }}>Index this patient's records</button>
            <div className="form-field"><label htmlFor="rag-question">Ask about the recorded evidence</label><textarea id="rag-question" value={ragQuestion} onChange={e=>setRagQuestion(e.target.value)} placeholder="Summarise the recorded observations and cite the source records." rows={3}/></div>
            <button className="button" disabled={busy || !ragStatus?.ready || ragQuestion.trim().length<3} onClick={async()=>{setBusy(true);setError("");try{setRagAnswer(await api<any>("/api/v1/patients/"+patient.id+"/rag/query",{method:"POST",body:JSON.stringify({question:ragQuestion,top_k:5})}));}catch(e:any){setError(e.message);}finally{setBusy(false);}}}>Ask local evidence assistant</button>
            {ragAnswer && <div className="context-report"><h4>Answer · {ragAnswer.model}</h4><p>{ragAnswer.answer}</p><h4>Retrieved evidence</h4>{(ragAnswer.sources||[]).map((source:any)=><div className="list-row" key={source.rank}><div><strong>[{source.rank}] {source.source_type} · {source.source_id}</strong><small>{source.text}</small><small>Relevance {Number(source.score).toFixed(3)} · SHA-256 {source.content_sha256}</small></div></div>)}<p className="muted">{ragAnswer.disclaimer}</p></div>}
            {contextReport && <div className="context-report"><h4>Deterministic fallback report</h4><p>{contextReport.observation_count} observations and {contextReport.fhir_resource_count} FHIR resources.</p></div>}
            <button className="button button-secondary" disabled={busy} onClick={() => void generateContext()}>Generate deterministic fallback report</button>
          </section>
        )}

        {!loading && patient && view === "snapshots" && (
          <section className="panel">
            <div className="panel-heading"><div><span className="eyebrow">APPEND-ONLY PATIENT STATE</span><h3>Twin snapshot versions</h3><p className="panel-copy">Each snapshot captures a canonical payload, SHA-256 checksum and source provenance.</p></div><button className="button" disabled={!permissions.can_write || busy} onClick={() => void createSnapshot()}>＋ Create new version</button></div>
            {snapshots.length === 0 ? <div className="empty-inline">There are no snapshot versions yet.</div> : snapshots.map(item => <div className="snapshot-card" key={item.id}><div className="snapshot-top"><div><strong>Snapshot v{item.version}</strong><p>{formatDate(item.created_at)} · {item.summary}</p></div><button className="button button-secondary" disabled={busy} onClick={() => void openSnapshot(item)}>Inspect artifact</button></div><code>{item.content_sha256 || "No checksum available"}</code></div>)}
            {selectedSnapshot && <div className="snapshot-detail"><div className="panel-heading"><div><span className="eyebrow">ARTIFACT INSPECTION</span><h3>Snapshot v{selectedSnapshot.version}</h3></div><span className={selectedSnapshot.integrity_verified ? "state-pill good" : "state-pill bad"}>{selectedSnapshot.integrity_verified ? "Checksum verified" : "Integrity check failed"}</span></div><p className="muted">SHA-256: {selectedSnapshot.content_sha256}</p><h4>Source provenance</h4><pre>{JSON.stringify(selectedSnapshot.provenance, null, 2)}</pre><h4>Snapshot payload</h4><pre>{JSON.stringify(selectedSnapshot.payload, null, 2)}</pre></div>}
          </section>
        )}

        {!loading && patient && view === "governance" && (
          <section className="panel">
            {!permissions.can_manage_access ? <div className="empty-state"><h3>Administrator access required</h3><p>Patient access grants and platform audit history are restricted to the twinfixeno-admin role.</p></div> : <>
              <div className="panel-heading"><div><span className="eyebrow">ACCESS CONTROL</span><h3>Patient access grants</h3><p className="panel-copy">Grant access using a Keycloak username or immutable subject ID.</p></div><span className="state-pill good">Administrator</span></div>
              <form className="grant-form" onSubmit={saveGrant}><label>Keycloak username<input value={grantUsername} onChange={event => setGrantUsername(event.target.value)} placeholder="clinician.username" /></label><label>Keycloak subject ID<input value={grantSubject} onChange={event => setGrantSubject(event.target.value)} placeholder="Optional subject UUID" /></label><label>Access level<select value={grantLevel} onChange={event => setGrantLevel(event.target.value as "read" | "write")}><option value="read">Read only</option><option value="write">Read and write</option></select></label><button className="button" disabled={busy || (!grantUsername.trim() && !grantSubject.trim())}>Save grant</button></form>
              {grants.map(item => <div className="list-row" key={item.id}><div><strong>{item.username || item.user_subject}</strong><small>{item.user_subject || "No subject binding"} · {item.access_level} access</small></div><button className="button button-danger" disabled={busy} onClick={() => void revokeGrant(item.id)}>Revoke</button></div>)}
              <div className="panel-heading history-heading"><div><span className="eyebrow">APPEND-ONLY APPLICATION EVENTS</span><h3>Recent audit activity</h3></div><span className="state-pill">{auditEvents.length} events</span></div>
              <div className="table-wrap"><table><thead><tr><th>Timestamp</th><th>Actor</th><th>Action</th><th>Resource</th></tr></thead><tbody>{auditEvents.map(item => <tr key={item.id}><td>{formatDate(item.created_at)}</td><td>{item.actor_username || "Unknown"}</td><td>{item.action}</td><td>{item.resource_type || "Patient"} {item.resource_id || item.patient_id || ""}</td></tr>)}{auditEvents.length === 0 && <tr><td colSpan={4}>No audit events recorded.</td></tr>}</tbody></table></div>
            </>}
          </section>
        )}

        <footer className="page-footer"><span>twinfixeno · Synthetic-data environment</span><span>Not a medical device · Not for diagnosis or treatment</span></footer>
      </main>
    </div>
  );
}
