"""MCP tools forward the caller's Keycloak bearer token; API enforces patient grants."""
import os, requests
from mcp.server.fastmcp import FastMCP, Context
API=os.getenv("TWINFIXENO_API_URL","http://api:8000").rstrip("/")
mcp=FastMCP(
    "TwinFixeno Clinical Twin",
    host="0.0.0.0",
    port=8001,
    stateless_http=True,
    json_response=True,
)
def invoke(ctx,method,path,body=None):
 headers=dict(ctx.request_context.request.headers); auth=headers.get("authorization") or headers.get("Authorization")
 if not auth or not auth.lower().startswith("bearer "): raise ValueError("Authenticated Keycloak bearer token required")
 r=requests.request(method,API+path,headers={"Authorization":auth,"Content-Type":"application/json"},json=body,timeout=120)
 if r.status_code>=400: raise ValueError(f"TwinFixeno API rejected request ({r.status_code}): {r.text[:400]}")
 return r.json() if r.content else {"status":"ok"}
@mcp.tool()
def get_patient_timeline(patient_id:int,ctx:Context)->dict:
 """Read an authorised patient's FHIR clinical timeline."""
 return invoke(ctx,"GET",f"/api/v1/patients/{patient_id}/timeline")
@mcp.tool()
def index_patient_evidence(patient_id:int,ctx:Context)->dict:
 """Index an authorised patient's records into private RAG; requires write access."""
 return invoke(ctx,"POST",f"/api/v1/patients/{patient_id}/rag/index")
@mcp.tool()
def ask_patient_evidence(patient_id:int,question:str,top_k:int=5,ctx:Context=None)->dict:
 """Ask a question grounded in authorised patient records and return cited evidence."""
 if ctx is None: raise ValueError("Authenticated MCP request context required")
 return invoke(ctx,"POST",f"/api/v1/patients/{patient_id}/rag/query",{"question":question,"top_k":top_k})
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
