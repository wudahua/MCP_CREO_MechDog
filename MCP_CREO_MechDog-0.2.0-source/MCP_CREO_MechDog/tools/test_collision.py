"""Verify an existing native model is refused, without changing its saved file."""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]


async def main():
    baseline = json.loads((ROOT / "build/mcp_integration_test.json").read_text(encoding="utf-8"))["job"]
    part = Path(baseline["result"]["part_file"])
    before = hashlib.sha256(part.read_bytes()).hexdigest()
    params = StdioServerParameters(command=sys.executable,args=[str(ROOT / "server.py")],cwd=ROOT)
    async with Client(params) as client:
        r = await client.call_tool("creo_create_plate", {"length":20,"width":20,"thickness":2,"model_name":baseline["spec"]["model_name"]})
        assert not r.is_error, r
        job_id = r.structured_content["job_id"]
        for _ in range(30):
            r = await client.call_tool("creo_get_job", {"job_id":job_id})
            assert not r.is_error, r
            job = r.structured_content
            if job["status"] not in ("queued","running"):
                break
            await asyncio.sleep(1)
        assert job["status"] == "failed", job
        assert "REFUSED_EXISTING_MODEL=1" in job.get("native_log_tail", ""), job
        assert before == hashlib.sha256(part.read_bytes()).hexdigest()
        report={"existing_model_refused":True,"saved_file_unchanged":True,"job":job}
        (ROOT / "build/mcp_collision_test.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps({"existing_model_refused":True,"saved_file_unchanged":True,"job_id":job_id}))


if __name__ == "__main__":
    asyncio.run(main())
