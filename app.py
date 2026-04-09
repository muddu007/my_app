import os
import asyncio
import aiohttp
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
import logging
import psutil
import ctypes
import threading

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "https://your-api-gateway.example.com")
API_KEY = os.getenv("API_KEY", "")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

# ── Memory spike state ─────────────────────────────────────────────────────────
_spike_holder = []   # keeps references so GC doesn't free the memory
_spike_lock = threading.Lock()


async def call_api_async(method: str, path: str, payload: dict = None):
    """Make an async HTTP call to the API Gateway."""
    url = f"{API_GATEWAY_URL}{path}"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if API_KEY:
        headers["x-api-key"] = API_KEY

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    logger.info(f"[ASYNC] {method} {url} | payload={payload}")

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.request(
            method=method,
            url=url,
            json=payload,
            headers=headers,
            ssl=False,
        ) as resp:
            status = resp.status
            try:
                data = await resp.json()
            except Exception:
                text = await resp.text()
                data = {"raw": text}
            logger.info(f"[ASYNC] Response {status}: {data}")
            return status, data


def run_async(coro):
    """Run an asyncio coroutine from a sync Flask context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def get_private_ip() -> str:
    """
    On AWS Fargate, fetch the private IP from the ECS Task Metadata v4 endpoint.
    Falls back to a simple socket-based approach for local dev.
    """
    # ECS Task Metadata Endpoint v4 (available on Fargate automatically)
    metadata_uri = os.getenv("ECS_CONTAINER_METADATA_URI_V4") or os.getenv("ECS_CONTAINER_METADATA_URI")
    if metadata_uri:
        try:
            import urllib.request, json as _json
            with urllib.request.urlopen(f"{metadata_uri}/task", timeout=2) as resp:
                task = _json.loads(resp.read())
            # Pull the first private IPv4 from the task's containers
            for container in task.get("Containers", []):
                for net in container.get("Networks", []):
                    ipv4s = net.get("IPv4Addresses", [])
                    if ipv4s:
                        return ipv4s[0]
        except Exception as e:
            logger.warning(f"ECS metadata fetch failed: {e}")

    # Local fallback — connect a UDP socket to get the outbound interface IP
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "unavailable"


def get_mem_info() -> dict:
    """Return memory usage for this process and the host."""
    vm = psutil.virtual_memory()
    proc = psutil.Process(os.getpid())
    proc_mem = proc.memory_info().rss  # resident set size in bytes

    return {
        "host_total_mb": round(vm.total / 1024 / 1024, 1),
        "host_used_mb": round(vm.used / 1024 / 1024, 1),
        "host_pct": vm.percent,                          # % of total host RAM used
        "proc_rss_mb": round(proc_mem / 1024 / 1024, 1),
        "proc_pct": round(proc_mem / vm.total * 100, 2), # this process's share of total RAM
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", gateway_url=API_GATEWAY_URL)


@app.route("/api/sysinfo", methods=["GET"])
def sysinfo():
    """Return memory usage of THIS server + its private IP."""
    mem = get_mem_info()
    private_ip = get_private_ip()
    return jsonify({
        "private_ip": private_ip,
        "mem": mem,
        "spike_active": len(_spike_holder) > 0,
    }), 200


@app.route("/api/mem/spike", methods=["POST"])
def mem_spike():
    """
    Allocate enough memory so that this process's share of host RAM
    increases by ~30 percentage points (capped so we don't OOM the container).
    Call again while active to release (toggle behaviour).
    """
    with _spike_lock:
        if _spike_holder:
            # Release the spike allocation
            _spike_holder.clear()
            logger.info("Memory spike RELEASED")
            return jsonify({"spike": False, "mem": get_mem_info()}), 200

        # Target: current proc RSS + 30% of total host RAM
        vm = psutil.virtual_memory()
        target_bytes = int(vm.total * 0.30)
        # Safety cap: don't use more than 80% of available free memory
        cap = int(vm.available * 0.80)
        alloc = min(target_bytes, cap)
        if alloc <= 0:
            return jsonify({"error": "Not enough free memory for spike"}), 500

        logger.info(f"Allocating {alloc / 1024 / 1024:.1f} MB for spike")
        try:
            chunk = bytearray(alloc)  # actually commits pages
            _spike_holder.append(chunk)
        except MemoryError:
            return jsonify({"error": "MemoryError during allocation"}), 500

        return jsonify({"spike": True, "allocated_mb": round(alloc / 1024 / 1024, 1), "mem": get_mem_info()}), 200


@app.route("/api/add", methods=["PUT"])
def add_click():
    body = request.get_json(silent=True) or {}
    status, data = run_async(call_api_async("PUT", "/add", body))
    return jsonify({"status": status, "data": data}), 200


@app.route("/api/del", methods=["PUT"])
def del_click():
    body = request.get_json(silent=True) or {}
    status, data = run_async(call_api_async("PUT", "/del", body))
    return jsonify({"status": status, "data": data}), 200


@app.route("/api/get", methods=["GET"])
def get_clicks():
    status, data = run_async(call_api_async("GET", "/get"))
    return jsonify({"status": status, "data": data}), 200


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )