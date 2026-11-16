"use client";
import {useEffect,useRef,useState} from "react";
import Keycloak from "keycloak-js";
type Patient={id:number;external_id:string;given_name:string;family_name:string;birth_date:string;sex:string};
type Observation={id:number;display:string;value:number;unit:string;observed_at:string};
type FhirStatus={available:boolean;fhir_version?:string;software?:string};
type TimelineItem={resource_type:string;resource_id:string;version_id?:string;title:string;status?:string;effective_at?:string;last_updated?:string};
const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://localhost:9080";
export default function Home(){
 const keycloak=useRef<Keycloak|null>(null);
 const [authenticated,setAuthenticated]=useState(false),[username,setUsername]=useState("");
 const [patient,setPatient]=useState<Patient|null>(null),[observations,setObservations]=useState<Observation[]>([]);
 const [snapshot,setSnapshot]=useState("No snapshot created yet"),[busy,setBusy]=useState(false),[error,setError]=useState("");
 const [fhirStatus,setFhirStatus]=useState<FhirStatus|null>(null),[fhirMessage,setFhirMessage]=useState("");
 const [timeline,setTimeline]=useState<TimelineItem[]>([]);
 useEffect(()=>{
  let alive=true;
  const client=new Keycloak({url:process.env.NEXT_PUBLIC_KEYCLOAK_URL||"http://localhost:8081",realm:process.env.NEXT_PUBLIC_KEYCLOAK_REALM||"twinfixeno",clientId:process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID||"twinfixeno-web"});
  keycloak.current=client;
  client.init({onLoad:"login-required",pkceMethod:"S256",checkLoginIframe:false}).then(async ok=>{
   if(!alive||!ok)return;
   setAuthenticated(true);setUsername(client.tokenParsed?.preferred_username as string||"Signed in");
   client.onTokenExpired=()=>{client.updateToken(30).catch(()=>client.login())};
   const headers={Authorization:`Bearer ${client.token}`};
   const response=await fetch(API+"/api/v1/patients",{headers});
   if(!response.ok)throw new Error("Patient API request failed");
   const patients:Patient[]=await response.json();
   if(!patients[0])throw new Error("No synthetic demo patient found");
   if(!alive)return;setPatient(patients[0]);
   const [obsResponse,fhirResponse]=await Promise.all([
    fetch(API+`/api/v1/patients/${patients[0].id}/observations`,{headers}),
    fetch(API+"/api/v1/integrations/fhir/status",{headers})
   ]);
   if(!obsResponse.ok)throw new Error("Observation API request failed");
   const obs:Observation[]=await obsResponse.json();
   if(alive){setObservations(obs);if(fhirResponse.ok)setFhirStatus(await fhirResponse.json());if(timelineResponse.ok){const t=await timelineResponse.json();setTimeline(t.items||[])}}
  }).catch(err=>{if(alive)setError(err?.message||"Authentication or API connection failed")});
  return ()=>{alive=false};
 },[]);
 async function createSnapshot(){
  if(!patient||!keycloak.current)return;setBusy(true);
  try{await keycloak.current.updateToken(30);const r=await fetch(API+`/api/v1/patients/${patient.id}/snapshots`,{method:"POST",headers:{Authorization:`Bearer ${keycloak.current.token}`}});
   if(!r.ok)throw Error("Snapshot request rejected");const s=await r.json();setSnapshot(`Snapshot #${s.version} · ${new Date(s.created_at).toLocaleString()}`)
  }catch{setError("Snapshot creation failed. Check your session and API logs.")}finally{setBusy(false)}
 }
 async function syncFhir(){if(!patient||!keycloak.current)return;setFhirMessage("Synchronising…");try{await keycloak.current.updateToken(30);const response=await fetch(API+`/api/v1/patients/${patient.id}/fhir/sync`,{method:"POST",headers:{Authorization:`Bearer ${keycloak.current.token}`}});if(!response.ok)throw Error("FHIR sync failed");const result=await response.json();const refreshed=await fetch(API+`/api/v1/patients/${patient.id}/timeline`,{headers:{Authorization:`Bearer ${keycloak.current.token}`}});if(refreshed.ok){const data=await refreshed.json();setTimeline(data.items||[])}setFhirMessage(`FHIR Patient ${result.patient_created?"created":"found"} · ${result.imported_count} clinical resources ingested`)}catch{setFhirMessage("FHIR sync failed. Check that HAPI FHIR is ready.")}}
 const value=(name:string)=>observations.find(o=>o.display===name);
 if(!authenticated)return <div className="auth-screen"><div className="auth-card"><div className="brand">twinfixeno</div><h1>Secure clinical workspace</h1><p>Connecting to Keycloak identity service…</p>{error&&<div className="notice">{error}</div>}</div></div>;
 return <div className="shell"><aside className="sidebar"><div className="brand">twinfixeno</div><div className="subbrand">Healthcare Digital Twin</div><nav className="nav"><div className="active">◈ Overview</div><div>◎ Patient registry</div><div>⌁ Clinical timeline</div><div>◇ Simulation studio</div><div>✳ AI copilot <span className="tag">planned</span></div><div>▤ Governance</div></nav><p style={{marginTop:45,fontSize:11,color:"#8da7ae",lineHeight:1.7}}>MVP 0.2.0<br/>Synthetic data environment</p></aside>
 <main className="main"><div className="topline"><div><div className="eyebrow">WORKSPACE / OVERVIEW</div><h1 className="heading">Patient command centre</h1><div className="muted">A longitudinal view of patient health context.</div></div><div className="user-tools"><span className="pill">● {username}</span><button className="secondary-button" onClick={()=>keycloak.current?.logout({redirectUri:window.location.origin})}>Sign out</button></div></div>{error&&<div className="notice">{error}</div>}
 <div className="grid"><div className="card"><div className="label">PATIENT TWINS</div><div className="metric">01</div><div className="muted">Synthetic patient profile</div></div><div className="card"><div className="label">OBSERVATIONS</div><div className="metric">{observations.length.toString().padStart(2,"0")}</div><div className="muted">Structured measurements</div></div><div className="card"><div className="label">TWIN SNAPSHOTS</div><div className="metric">{snapshot.startsWith("Snapshot")?"01":"00"}</div><div className="muted">Versioned patient states</div></div><div className="card"><div className="label">FHIR R4 SERVER</div><div className="metric" style={{fontSize:20}}>{fhirStatus?.available?"Connected":"Checking…"}</div><div className="muted">{fhirStatus?.fhir_version? "FHIR "+fhirStatus.fhir_version:"HAPI FHIR endpoint"}</div></div></div>
 <section className="section"><div className="sectionhead"><h2>Patient digital twin</h2><span className="tag">SYNTHETIC RECORD</span></div><div className="card"><div className="topline"><div className="patient"><div className="avatar">{patient?patient.given_name[0]+patient.family_name[0]:"--"}</div><div><strong>{patient?`${patient.given_name} ${patient.family_name}`:"Loading patient…"}</strong><div className="muted">{patient?patient.external_id+" · "+patient.sex+" · Born "+patient.birth_date:"Fetching demo record"}</div></div></div><div className="action-stack"><button className="secondary-button" onClick={syncFhir} disabled={!patient}>↗ Sync to FHIR</button><button className="button" onClick={createSnapshot} disabled={!patient||busy}>{busy?"Creating…":"＋ Create twin snapshot"}</button></div></div><div className="grid" style={{gridTemplateColumns:"repeat(3,1fr)"}}><div><div className="label">HEART RATE</div><div className="metric">{value("Heart rate")?.value??"—"} <small>bpm</small></div></div><div><div className="label">BLOOD PRESSURE</div><div className="metric">{value("Systolic blood pressure")?.value??"—"}<small> / {value("Diastolic blood pressure")?.value??"—"} mmHg</small></div></div><div><div className="label">BODY WEIGHT</div><div className="metric">{value("Body weight")?.value??"—"} <small>kg</small></div></div></div></div></section>
 <section className="section"><div className="sectionhead"><h2>Latest observations</h2><span className="muted">Synthetic seed dataset</span></div><div className="card">{observations.map(o=><div className="row" key={o.id}><div><strong>{o.display}</strong><div className="label">{new Date(o.observed_at).toLocaleDateString()}</div></div><strong>{o.value} {o.unit}</strong></div>)}</div></section>
 <section className="section"><div className="sectionhead"><h2>Clinical timeline</h2><span className="muted">{timeline.length} FHIR resources · Observation / Condition / Encounter</span></div><div className="card">{timeline.length===0?<div className="muted">No FHIR clinical resources imported yet. Use “Sync to FHIR” to import resources associated with this patient.</div>:timeline.map((item,index)=><div className="row" key={item.resource_type+item.resource_id+index}><div><div><strong>{item.title}</strong> <span className="tag">{item.resource_type}</span></div><div className="muted">{item.effective_at?new Date(item.effective_at).toLocaleString():"Date not recorded"} · {item.status||"status unknown"}</div></div><span className="label">v{item.version_id||"—"}</span></div>)}</div></section>
 <section className="section"><div className="sectionhead"><h2>Twin state</h2><span className="tag">VERSIONED</span></div><div className="card"><div className="row"><div><strong>Latest snapshot</strong><div className="muted">{snapshot}</div></div><span className="tag">Descriptive</span></div><div className="notice">Synthetic data and descriptive calculations only. This prototype is not a medical device and must not be used for diagnosis or treatment.</div></div></section></main></div>;
}
