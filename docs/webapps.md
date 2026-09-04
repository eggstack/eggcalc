# Web Applications

eggcalc is optimized for web applications with thread-safety, caching, and async support.

## Basic Setup

```python
from eggcalc import EggCalcApp, EvaluationError

app = EggCalcApp(cache_size=1000)

def calculate(expression: str):
    try:
        result = app.calculate(expression)
        return {"success": True, "result": str(result)}
    except EvaluationError as e:
        return {"success": False, "error": str(e)}
```

## FastAPI Example

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from eggcalc import EggCalcApp, EvaluationError, TimeoutError

app = FastAPI()
calc = EggCalcApp(cache_size=1000)

class CalculateRequest(BaseModel):
    expression: str
    timeout: float = 1.0

class CalculateResponse(BaseModel):
    result: str
    cached: bool

@app.post("/calculate", response_model=CalculateResponse)
async def calculate(req: CalculateRequest):
    try:
        result = await calc.calculate_async(req.expression)
        return CalculateResponse(
            result=str(result),
            cached=calc.cache_size > 0
        )
    except EvaluationError as e:
        raise HTTPException(400, str(e))
    except TimeoutError:
        raise HTTPException(408, "Evaluation timed out")
```

## Flask Example

```python
from flask import Flask, request, jsonify
from eggcalc import EggCalcApp, EvaluationError

app = Flask(__name__)
calc = EggCalcApp(cache_size=1000)

@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.get_json()
    expression = data.get("expression", "")
    
    try:
        result = calc.calculate(expression)
        return jsonify({"result": str(result)})
    except EvaluationError as e:
        return jsonify({"error": str(e)}), 400
```

## Django Example

```python
# views.py
from django.http import JsonResponse
from django.views import View
import json
from eggcalc import EggCalcApp, EvaluationError

calc = EggCalcApp(cache_size=1000)

class CalculateView(View):
    def post(self, request):
        data = json.loads(request.body)
        expression = data.get("expression", "")
        
        try:
            result = calc.calculate(expression)
            return JsonResponse({"result": str(result)})
        except EvaluationError as e:
            return JsonResponse({"error": str(e)}, status=400)
```

## Thread Safety

`EggCalcApp` is thread-safe:

- Constants and functions are isolated per instance
- Internal state uses thread-safe locks
- Safe for concurrent requests

```python
from eggcalc import EggCalcApp

# Each instance has isolated state
app1 = EggCalcApp()
app2 = EggCalcApp()

app1.register_constant("x", 10)
app2.register_constant("x", 20)

print(app1.calculate("x"))  # 10
print(app2.calculate("x"))  # 20
```

## Caching

Enable caching for repeated expressions:

```python
from eggcalc import EggCalcApp

# LRU cache with 1000 entries
app = EggCalcApp(cache_size=1000)
app_without_storage = EggCalcApp(cache_size=0)  # Computes without caching

# First call computes
result = app.calculate("complex expression")

# Second call uses cache (instant)
result = app.calculate("complex expression")

# Check cache
print(app.cache_size)  # 1

# Clear cache
app.clear_cache()
```

Registering or re-registering an instance constant/function clears that
instance's cache, preventing stale values after runtime configuration changes.

## Timeout Protection

For untrusted input, use timeout:

```python
from eggcalc import evaluate_with_timeout, TimeoutError

def safe_calculate(expr: str, timeout: float = 1.0):
    try:
        return evaluate_with_timeout(expr, timeout)
    except TimeoutError:
        return None
```

## Rate Limiting Example

```python
from functools import wraps
from time import time
from collections import defaultdict
from eggcalc import EggCalcApp, EvaluationError

calc = EggCalcApp()
request_times = defaultdict(list)

def rate_limit(max_per_minute: int):
    def decorator(func):
        @wraps(func)
        def wrapper(ip: str, *args, **kwargs):
            now = time()
            times = request_times[ip]
            times[:] = [t for t in times if now - t < 60]
            
            if len(times) >= max_per_minute:
                raise Exception("Rate limit exceeded")
            
            times.append(now)
            return func(*args, **kwargs)
        return wrapper
    return decorator

@rate_limit(max_per_minute=60)
def calculate(ip: str, expression: str):
    return calc.calculate(expression)
```

## Performance Tips

1. **Use caching**: Enable for repeated expressions
2. **Pre-normalize**: Use `evaluate()` for pre-formatted input
3. **Instance isolation**: Create separate instances for different configs
4. **Connection pooling**: Reuse app instance across requests

| Method | Input | Performance |
|--------|-------|-------------|
| `evaluate()` | Pre-normalized | Fastest (skips normalization) |
| `evaluate_raw()` | Raw input | Full pipeline cost |
| `evaluate_cached()` | With cache | O(1) after first |
| `EggCalcApp.calculate()` | With cache | O(1) after first |

See [api.md](api.md#performance-notes) for ballpark timings.

## Error Handling

```python
from eggcalc import (
    EggCalcApp,
    EvaluationError,
    TimeoutError,
)

app = EggCalcApp()

def safe_evaluate(expr: str):
    try:
        result = app.calculate(expr)
        return {"success": True, "result": str(result)}
    except EvaluationError as e:
        return {"success": False, "error": str(e), "type": "evaluation"}
    except TimeoutError:
        return {"success": False, "error": "Timeout", "type": "timeout"}
    except Exception as e:
        return {"success": False, "error": str(e), "type": "unknown"}
```

## AI Agent Integration (MCP)

For AI agent workflows, eggcalc includes an MCP (Model Context Protocol) server that exposes text and math tools:

```bash
calc --mcp
```

The MCP server provides 83 tools for AI agent use across text analysis, validation, unit conversion, and more.

See [MCP Server](mcp.md) for full documentation.

### MCP in Web Applications

If your webapp serves AI agents, you can proxy MCP requests:

```python
from fastapi import FastAPI
import subprocess
import json

app = FastAPI()

@app.post("/mcp")
async def mcp_proxy(request: dict):
    # Start calc MCP server
    process = subprocess.Popen(
        ["calc", "--mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Send request
    response_bytes = process.communicate(input=json.dumps(request).encode())[0]
    return json.loads(response_bytes.decode())
```

**Security note:** The MCP server enforces input limits (100K text, 10K list items) to prevent DoS attacks.
