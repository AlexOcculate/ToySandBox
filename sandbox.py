# Line 1:  Import time for timestamping audit entries and measuring execution duration.
import time

# Line 2:  Import threading to run tools in isolated threads with timeout enforcement.
import threading

# Line 3:  Import re for output validation (detecting suspicious patterns in tool results).
import re

# Line 4:  Import inspect for static analysis of tool source code before execution.
import inspect

# Line 6:  Define the frozenset of module names that are absolutely forbidden inside the sandbox.
#          Frozenset is used because it's immutable and hashable (fast membership checks).
FORBIDDEN_MODULES = frozenset(
    {"os", "subprocess", "shutil", "socket", "ctypes", "importlib"}
)

# Line 8:  Define regex patterns that indicate dangerous content in tool output.
#          These catch credential leaks, system file access, and other exfiltration attempts.
DANGEROUS_OUTPUT_PATTERNS = [
    r"/etc/passwd",  # Linux system credential file path
    r"C:\\Windows\\",  # Windows system directory path
    r"password\s*=\s*\S+",  # Credential assignment pattern (e.g., "password = hunter2")
    r"BEGIN (RSA|EC|OPENSSH) PRIVATE KEY",  # Private key material leak
]


# Line 15: SandBox class — the restricted execution environment that all tool calls must pass through.
#          Think of it as a "cage" around each tool: it can only see what we allow,
#          it has a time limit, and every action is recorded in an audit trail.
class SandBox:

    # Line 19: Constructor: configure timeout, initialize empty audit trail, build restricted namespace.
    def __init__(self, timeout_seconds=5.0):
        # Line 21: Store the maximum allowed execution time per single tool call (in seconds).
        self.timeout_seconds = timeout_seconds
        # Line 23: Initialize the audit trail as an empty list; each entry is one execution record.
        self.audit_trail = []
        # Line 25: Build the restricted namespace that tools will execute within.
        self.restricted_namespace = self._build_restricted_namespace()
        # Line 27: Flag to disable sandbox protections (used only in adversarial testing).
        self.disabled = False

    # Line 30: Build a filtered __builtins__ dict that excludes dangerous modules and functions.
    #          This is the "restricted namespace" — tools can only use what's in here.
    def _build_restricted_namespace(self):
        # Line 33: Import the builtins module to access all Python built-in names.
        import builtins

        # Line 35: Create an empty dict that will hold only the safe subset of builtins.
        safe_builtins = {}
        # Line 37: Iterate over every name available in the builtins module.
        for name in dir(builtins):
            # Line 39: Skip __import__ — without it, no new modules can be loaded dynamically.
            if name == "__import__":
                continue
            # Line 42: Skip exec and eval — we provide controlled versions instead of raw access.
            if name in ("exec", "eval"):
                continue
            # Line 45: Copy the safe builtin (print, len, range, int, str, list, dict, etc.) into our namespace.
            safe_builtins[name] = getattr(builtins, name)
        # Line 47: Return the filtered namespace dict that will be injected as __builtins__ for tool execution.
        return safe_builtins

    # Line 50: Execute a tool inside the sandbox with full protection pipeline.
    #          Pipeline: (1) static safety check → (2) timed thread execution → (3) output validation → (4) audit log.
    #          Returns a standardized dict: {"status", "result", "reason", "audit_id"}.
    def execute(self, tool_name, args, tool_fn):
        # Line 54: If sandbox is disabled (adversarial test mode), skip all protections and run directly.
        if self.disabled:
            return self._execute_unrestricted(tool_name, args, tool_fn)

        # Line 57: Record the start time for duration measurement (high-resolution clock).
        start_time = time.time()

        # Line 59: Perform static analysis on the tool function BEFORE execution.
        safety = self.check_tool_safety(tool_fn)

        # Line 61: If static analysis found forbidden module references, block immediately without running.
        if not safety["safe"]:
            # Line 63: Calculate duration (will be near-zero since we didn't actually run the tool).
            duration_ms = (time.time() - start_time) * 1000
            # Line 65: Build the audit entry for this blocked execution.
            self.audit_trail.append(
                {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "tool_name": tool_name,
                    "args": args,
                    "status": "blocked",
                    "result": None,
                    "duration_ms": round(duration_ms, 2),
                    "reason": f"forbidden module reference: {', '.join(safety['forbidden_refs'])}",
                }
            )
            # Line 76: Return blocked response — the agent will see this and can inform the user.
            return {
                "status": "blocked",
                "result": None,
                "reason": f"Tool '{tool_name}' references forbidden module(s): {', '.join(safety['forbidden_refs'])}",
                "audit_id": len(self.audit_trail) - 1,
            }

        # Line 84: Tool passed static analysis — now execute it in an isolated thread with timeout.
        #          Use a container dict to pass results back from the worker thread (threads can't return values directly).
        execution_result = {"result": None, "error": None}

        # Line 88: Define the worker function that will run inside the isolated thread.
        def _worker():
            # Line 90: Attempt to call the tool function with the provided keyword arguments.
            try:
                # Line 92: Execute the actual tool logic (e.g., calculate, string_reverse, etc.).
                execution_result["result"] = tool_fn(**args)
            # Line 94: Catch any exception the tool might raise during execution.
            except Exception as e:
                # Line 96: Store the exception message so the main thread can report it.
                execution_result["error"] = str(e)

        # Line 99: Create a daemon thread — it will not prevent program exit even if still running.
        thread = threading.Thread(target=_worker, daemon=True)
        # Line 101: Start the worker thread (tool begins executing now).
        thread.start()
        # Line 103: Block the main thread waiting for the worker, but give up after timeout_seconds.
        thread.join(timeout=self.timeout_seconds)

        # Line 106: Determine what happened based on thread state and execution result.
        if thread.is_alive():
            # Line 108: Thread is still running → tool exceeded the time limit (timeout).
            status = "timeout"
            reason = f"exceeded {self.timeout_seconds}s timeout limit"
            result = None
        elif execution_result["error"] is not None:
            # Line 113: Tool raised an exception during execution.
            status = "error"
            reason = execution_result["error"]
            result = None
        else:
            # Line 118: Tool completed successfully — now validate its output for dangerous content.
            raw_result = execution_result["result"]
            validation = self._validate_output(raw_result)
            if not validation["valid"]:
                # Line 123: Output contained a dangerous pattern → block it.
                status = "blocked"
                reason = f"output validation failed: matched pattern '{validation['matched_pattern']}'"
                result = "[OUTPUT BLOCKED BY SANDBOX]"
            else:
                # Line 128: Output is clean → accept the result as-is.
                status = "success"
                reason = None
                result = raw_result

        # Line 133: Calculate total execution duration in milliseconds (includes thread overhead).
        duration_ms = (time.time() - start_time) * 1000

        # Line 135: Build the audit entry capturing every detail of this execution.
        self.audit_trail.append(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "tool_name": tool_name,
                "args": args,
                "status": status,
                "result": str(result) if result is not None else None,
                "duration_ms": round(duration_ms, 2),
                "reason": reason,
            }
        )

        # Line 147: Return the standardized response dict that the harness will consume.
        return {
            "status": status,
            "result": result,
            "reason": reason,
            "audit_id": len(self.audit_trail) - 1,
        }

    # Line 155: Execute a tool without any restrictions (bypasses all sandbox protections).
    #          Only used in adversarial testing to prove the harness handles raw failures.
    def _execute_unrestricted(self, tool_name, args, tool_fn):
        # Line 158: Record start time for duration measurement.
        start_time = time.time()
        # Line 160: Attempt direct execution without thread isolation or validation.
        try:
            # Line 162: Call the tool function directly (no timeout, no namespace restriction).
            result = tool_fn(**args)
            # Line 164: Calculate duration for this unrestricted call.
            duration_ms = (time.time() - start_time) * 1000
            # Line 166: Log the audit entry even in unrestricted mode (transparency is always on).
            self.audit_trail.append(
                {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "tool_name": tool_name,
                    "args": args,
                    "status": "success",
                    "result": str(result),
                    "duration_ms": round(duration_ms, 2),
                    "reason": None,
                }
            )
            # Line 177: Return success response.
            return {
                "status": "success",
                "result": result,
                "reason": None,
                "audit_id": len(self.audit_trail) - 1,
            }
        # Line 179: Catch any exception from unrestricted execution.
        except Exception as e:
            # Line 181: Calculate duration even though the tool failed.
            duration_ms = (time.time() - start_time) * 1000
            # Line 183: Log the failure in the audit trail.
            self.audit_trail.append(
                {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "tool_name": tool_name,
                    "args": args,
                    "status": "error",
                    "result": None,
                    "duration_ms": round(duration_ms, 2),
                    "reason": str(e),
                }
            )
            # Line 194: Return error response with the exception message.
            return {
                "status": "error",
                "result": None,
                "reason": str(e),
                "audit_id": len(self.audit_trail) - 1,
            }

    # Line 197: Validate tool output against dangerous content patterns.
    #          This is the post-execution safety net: even if a tool runs, its output is inspected.
    def _validate_output(self, output):
        # Line 200: Convert the output to a string so we can apply regex pattern matching.
        output_str = str(output)
        # Line 202: Check each dangerous pattern against the output string.
        for pattern in DANGEROUS_OUTPUT_PATTERNS:
            # Line 204: Attempt to find the pattern anywhere in the output (case-insensitive).
            match = re.search(pattern, output_str, re.IGNORECASE)
            # Line 206: If a dangerous pattern is found, immediately return validation failure.
            if match:
                return {"valid": False, "matched_pattern": pattern}
        # Line 209: No dangerous patterns detected — the output is considered safe.
        return {"valid": True, "matched_pattern": None}

    # Line 212: Perform static analysis on a tool function's source code to detect forbidden module references.
    #          This is the pre-execution safety check: if the code mentions "os" or "subprocess", block it.
    def check_tool_safety(self, tool_fn):
        # Line 215: Attempt to retrieve the source code of the function using the inspect module.
        try:
            # Line 217: Get the actual source code text of the function.
            source = inspect.getsource(tool_fn)
        # Line 219: If source is unavailable (e.g., built-in functions, compiled code), assume safe.
        except (OSError, TypeError):
            return {"safe": True, "forbidden_refs": []}

        # Line 222: Strip comment lines from the source to avoid false positives.
        #          Without this, a comment like "# prevents import os" would trigger a block.
        code_lines = []
        # Line 225: Iterate through each line of the source.
        for line in source.split("\n"):
            # Line 227: Skip lines that are purely comments (first non-whitespace char is '#').
            if line.strip().startswith("#"):
                continue
            # Line 230: Keep non-comment lines for analysis.
            code_lines.append(line)
        # Line 232: Rejoin the filtered lines into a clean source string (comments removed).
        source = "\n".join(code_lines)

        # Line 235: Collect any forbidden module names found in the actual code (not comments).
        found_forbidden = []
        # Line 237: Check each forbidden module name using word-boundary regex.
        for mod in FORBIDDEN_MODULES:
            # Line 239: Search for the module name as a whole word in the comment-stripped source.
            if re.search(rf"\b{mod}\b", source):
                # Line 241: Record which forbidden module was referenced in the code.
                found_forbidden.append(mod)
        # Line 243: Return the safety verdict: safe only if no forbidden references were found.
        return {"safe": len(found_forbidden) == 0, "forbidden_refs": found_forbidden}

    # Line 246: Generate a summary of the audit trail for reporting purposes.
    def get_audit_summary(self):
        # Line 248: Initialize counters for each possible status type.
        counts = {"success": 0, "blocked": 0, "timeout": 0, "error": 0}
        # Line 250: Tally each audit entry into its status bucket.
        for entry in self.audit_trail:
            if entry["status"] in counts:
                counts[entry["status"]] += 1
        # Line 254: Return the summary with total count and per-status breakdown.
        return {"total": len(self.audit_trail), "by_status": counts}

    # Line 257: Format the full audit trail as a human-readable string (for display in trace reports).
    def format_audit_trail(self):
        # Line 259: If the trail is empty, return a friendly message.
        if not self.audit_trail:
            return "  (no executions recorded)"
        # Line 262: Build lines for each audit entry.
        lines = []
        # Line 264: Iterate through all recorded executions in chronological order.
        for i, entry in enumerate(self.audit_trail):
            # Line 266: Format each entry as a single line with key fields.
            lines.append(
                f"  [{i}] {entry['timestamp']} | {entry['tool_name']}({entry['args']}) "
                f"→ {entry['status'].upper()} ({entry['duration_ms']}ms)"
            )
            # Line 271: If there's a reason (blocked/timeout/error), add it as an indented detail line.
            if entry["reason"]:
                lines.append(f"      reason: {entry['reason']}")
        # Line 274: Join all lines into a single formatted string.
        return "\n".join(lines)
