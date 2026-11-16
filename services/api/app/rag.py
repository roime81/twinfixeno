"""Patient-scoped local RAG using Ollama embeddings/chat and Qdrant."""
import hashlib, os, uuid, requests
from datetime import datetime, timezone
from sqlalchemy import select
from .models import Patient, Observation, FhirClinicalResource, TwinSnapshot, TwinSnapshotArtifact
OLLAMA=os.getenv("OLLAMA_URL","http://ollama:11434").rstrip("/")
QDRANT=os.getenv("QDRANT_URL","http://qdrant:6333").rstrip("/")
COLLECTION=os.getenv("QDRANT_COLLECTION","twinfixeno_clinical")
EMBED=os.getenv("OLLAMA_EMBED_MODEL","nomic-embed-text")
CHAT=os.getenv("OLLAMA_CHAT_MODEL","qwen2.5:3b")
TIMEOUT=int(os.getenv("AI_REQUEST_TIMEOUT","120"))
def call(method,url,**kw):
 r=requests.request(method,url,timeout=TIMEOUT,**kw); r.raise_for_status(); return r
def ai_status():
 s={"ollama":False,"qdrant":False,"chat_model":CHAT,"embedding_model":EMBED}
 try:
  names={x.get("name") for x in call("GET",OLLAMA+"/api/tags").json().get("models",[])}
  s.update(ollama=True,chat_model_ready=any(n==CHAT or n.startswith(CHAT+":") for n in names if n),embedding_model_ready=any(n==EMBED or n.startswith(EMBED+":") for n in names if n))
 except requests.RequestException as e:s["ollama_error"]=str(e)
 try:call("GET",QDRANT+"/collections");s["qdrant"]=True
 except requests.RequestException as e:s["qdrant_error"]=str(e)
 s["ready"]=bool(s["ollama"] and s["qdrant"] and s.get("chat_model_ready") and s.get("embedding_model_ready"));return s
def embed(t):return call("POST",OLLAMA+"/api/embed",json={"model":EMBED,"input":t}).json()["embeddings"][0]
def ensure(size):
 cs=call("GET",QDRANT+"/collections").json().get("result",{}).get("collections",[])
 if not any(x["name"]==COLLECTION for x in cs):call("PUT",QDRANT+"/collections/"+COLLECTION,json={"vectors":{"size":size,"distance":"Cosine"}})
def chunks(db,pid):
 p=db.get(Patient,pid)
 if not p:raise ValueError("Patient not found")
 out=[{"source_type":"Patient","source_id":p.external_id,"text":f"Patient {p.external_id}; {p.given_name} {p.family_name}; DOB {p.birth_date}; sex {p.sex}."}]
 for x in db.scalars(select(Observation).where(Observation.patient_id==pid)).all():out.append({"source_type":"Observation","source_id":str(x.id),"text":f"{x.display} ({x.code}): {x.value} {x.unit}, observed {x.observed_at}."})
 for x in db.scalars(select(FhirClinicalResource).where(FhirClinicalResource.patient_id==pid)).all():
  r=x.resource_json or {}; coding=(r.get("code",{}).get("coding") or [{}])[0]; label=r.get("code",{}).get("text") or coding.get("display") or x.resource_type
  out.append({"source_type":x.resource_type,"source_id":x.fhir_id,"text":f"{x.resource_type} {label}; status {x.status}; effective {x.effective_at}; source {x.source_system}; version {x.version_id}."})
 for snap in db.scalars(select(TwinSnapshot).where(TwinSnapshot.patient_id==pid)).all():
  a=db.scalar(select(TwinSnapshotArtifact).where(TwinSnapshotArtifact.snapshot_id==snap.id))
  if a:out.append({"source_type":"TwinSnapshot","source_id":str(snap.id),"text":f"Snapshot v{snap.version}: {snap.summary}. Payload {str(a.payload)[:5000]}"})
 return out
def index_patient(db,pid):
 items=chunks(db,pid)
 if not items:return {"patient_id":pid,"indexed":0}
 vectors=[embed(x["text"]) for x in items];ensure(len(vectors[0]));points=[]
 for x,v in zip(items,vectors):
  digest=hashlib.sha256(x["text"].encode()).hexdigest(); ident=str(uuid.uuid5(uuid.NAMESPACE_URL,f"twinfixeno:{pid}:{x['source_type']}:{x['source_id']}"))
  points.append({"id":ident,"vector":v,"payload":{"patient_id":pid,**x,"content_sha256":digest,"indexed_at":datetime.now(timezone.utc).isoformat()}})
 call("PUT",QDRANT+f"/collections/{COLLECTION}/points?wait=true",json={"points":points})
 return {"patient_id":pid,"indexed":len(points),"collection":COLLECTION,"embedding_model":EMBED}
def answer_patient(db,pid,question,top_k=5):
 if not db.get(Patient,pid):raise ValueError("Patient not found")
 v=embed(question);ensure(len(v))
 matches=call("POST",QDRANT+f"/collections/{COLLECTION}/points/search",json={"vector":v,"limit":top_k,"with_payload":True,"filter":{"must":[{"key":"patient_id","match":{"value":pid}}]}}).json().get("result",[])
 if not matches:return {"answer":"No indexed evidence. Index this patient's records first.","sources":[],"grounded":False,"model":CHAT}
 context="\n".join(f"[{i+1}] {x['payload']['source_type']} {x['payload']['source_id']}: {x['payload']['text']}" for i,x in enumerate(matches))
 prompt=("Answer only from supplied patient records. Do not diagnose, recommend treatment, infer missing facts or claim causality. State when evidence is insufficient. Cite records as [1], [2]. Synthetic-data demonstration only.\n\n"+context+"\n\nQuestion: "+question)
 answer=call("POST",OLLAMA+"/api/chat",json={"model":CHAT,"stream":False,"messages":[{"role":"user","content":prompt}],"options":{"temperature":0.1,"num_ctx":4096}}).json().get("message",{}).get("content","")
 return {"answer":answer,"model":CHAT,"embedding_model":EMBED,"grounded":True,"sources":[{"rank":i+1,"source_type":x["payload"]["source_type"],"source_id":x["payload"]["source_id"],"score":x["score"],"content_sha256":x["payload"]["content_sha256"],"text":x["payload"]["text"]} for i,x in enumerate(matches)],"disclaimer":"Synthetic-data demonstration only. Not a diagnosis, treatment recommendation or clinical decision-support output."}
