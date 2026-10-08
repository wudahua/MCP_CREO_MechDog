"""Real MCP + Creo integration tests of general native parametric modeling."""
import asyncio,json,math,sys,time
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from version import VERSION
report={"version":VERSION,"cases":[],"started_at":time.time()}

async def call(client,name,args):
    r=await client.call_tool(name,args)
    if r.is_error: raise RuntimeError(f"{name}: {r.content}")
    return r.structured_content

async def job(client,name,args,expect_success=True):
    created=await call(client,name,args)
    print(f"{name} job={created['job_id']} model={created.get('model_id')}",flush=True)
    for i in range(330):
        result=await call(client,"creo_get_job",{"job_id":created["job_id"]})
        if result["status"] not in ("queued","running"):
            break
        await asyncio.sleep(1)
    report["cases"].append({"tool":name,"args":args,"job":result})
    (ROOT/"build/general_integration_test.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"result={result['status']} stage={result.get('stage')} message={result.get('message')}",flush=True)
    if expect_success:
        assert result["status"]=="succeeded",str((result.get("message"),result.get("job_id")))
    return result

def rectangle(name,x0,y0,x1,y1):
    return {"type":"rectangle","name":name,"min":[x0,y0],"max":[x1,y1]}

async def main():
    async with Client(StdioServerParameters(command=sys.executable,args=[str(ROOT/"server.py")],cwd=ROOT),read_timeout_seconds=60) as client:
        tools=await client.list_tools()
        report["tools"]=[t.name for t in tools.tools]
        report["protocol_version"]=client.protocol_version
        print("tools="+str(len(report["tools"])),flush=True)
        status=await call(client,"creo_session_status",{})
        assert status["connected"],status
        # A circular sketch + separate extrusion, then a real diameter edit.
        created=await job(client,"creo_new_part",{})
        mid=created["model_id"]; rev=created["revision"]
        sk=await job(client,"creo_create_sketch",{"model_id":mid,"expected_revision":rev,"label":"disk_profile","entities":[{"type":"circle","name":"disk","center":[0,0],"radius":8}],"dimensions":[{"name":"diameter","type":"diameter","refs":[{"entity":"disk"}],"value":16,"position":[12,0]}]})
        ex=await job(client,"creo_extrude",{"model_id":mid,"expected_revision":sk["revision"],"label":"disk_solid","sketch":"disk_profile","depth":10})
        volume=ex["result"]["inspection"]["volume_mm3"]
        assert abs(volume-math.pi*64*10)<0.01,volume
        assert abs(ex["result"]["inspection"]["bodies"][0]["bbox"][0][2])<1e-6
        assert abs(ex["result"]["inspection"]["bodies"][0]["bbox"][1][2]-10)<1e-6
        edited=await job(client,"creo_set_sketch_dimensions",{"model_id":mid,"expected_revision":ex["revision"],"sketch":"disk_profile","values":{"diameter":20}})
        assert abs(edited["result"]["inspection"]["volume_mm3"]-math.pi*100*10)<0.01
        # A non-rectangular L profile and additive extrusion on another principal plane.
        lprofile=[[-20,-15],[20,-15],[20,0],[0,0],[0,15],[-20,15]]
        bracket_ops=[
            {"op":"sketch","label":"l_profile","plane":"XY","entities":[{"type":"polyline","name":"outline","points":lprofile,"closed":True}]},
            {"op":"extrude","label":"l_base","sketch":"l_profile","depth":8},
            {"op":"sketch","label":"wall_profile","plane":"XZ","offset":15,"entities":[rectangle("wall",-20,0,0,25)]},
            {"op":"extrude","label":"wall","sketch":"wall_profile","depth":10},
        ]
        bracket=await job(client,"creo_execute_plan",{"operations":bracket_ops,"assertions":{"volume_mm3":10600,"require_solid":True}})
        print("BRACKET_VOLUME="+str(bracket["result"]["inspection"]["volume_mm3"]),flush=True)
        print("BRACKET_BBOX="+str(bracket["result"]["inspection"]["bodies"]),flush=True)
        # A stepped turned part, axial through hole, blind hole and revolved groove.
        turn_ops=[
            {"op":"sketch","label":"turn_profile","plane":"XZ","entities":[
                {"type":"polyline","name":"section","points":[[0,0],[12,0],[12,6],[8,6],[8,30],[0,30]],"closed":True},
                {"type":"centerline","name":"axis","start":[0,-5],"end":[0,35]}]},
            {"op":"revolve","label":"turn","sketch":"turn_profile","angle":360},
            {"op":"hole","label":"bore","diameter":6,"placement":{"kind":"plane","axis":"z","offset":30},"reference1":{"kind":"datum_plane","axis":"x"},"reference2":{"kind":"datum_plane","axis":"y"}},
            {"op":"hole","label":"blind","diameter":2,"depth":5,"placement":{"kind":"plane","axis":"z","offset":30},"reference1":{"kind":"datum_plane","axis":"x"},"reference2":{"kind":"datum_plane","axis":"y"},"offset1":5},
            {"op":"sketch","label":"groove_profile","plane":"XZ","entities":[rectangle("groove",6,16,10,20),{"type":"centerline","name":"axis","start":[0,0],"end":[0,30]}]},
            {"op":"revolve","label":"groove","sketch":"groove_profile","mode":"cut","angle":360},
        ]
        turned=await job(client,"creo_execute_plan",{"operations":turn_ops,"assertions":{"volume_mm3":2013*math.pi,"require_solid":True}})
        report["main_models"]={"disk":mid,"bracket":bracket["model_id"],"turned":turned["model_id"]}
        report["success"]=True
        (ROOT/"build/general_integration_test.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print("GENERAL_CORE_SUCCESS=1",flush=True)

if __name__=="__main__": asyncio.run(main())
