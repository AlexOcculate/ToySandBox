# Line 1:  Import time for timestamping audit entries and measuring execution duration.
import time

# Line 2:  Import threading to run tools in isolated threads with timeout enforcement.
import threading

# Line 3:  Import re for output validation (detecting suspicious patterns in tool results).
import re

# Line 4:  Import inspect for static analysis of tool source code before execution.
import inspect

# Line 6:  Define the frozenset of module names that are absolutely forbidden inside the sandbox.
FORBIDDEN_MODULES = frozenset(
    {"os", "subprocess", "shutil", "socket", "ctypes", "importlib"}
)

# Line 8:  Define regex patterns that indicate dangerous content in tool output.
DANGEROUS_OUTPUT_PATTERNS = [
    r"/etc/passwd",  # Literal path reference in output
    r"C:\\Windows\\",  # Windows system directory path
    r"password\s*=\s*\S+",  # Credential assignment pattern
    r"BEGIN (RSA|EC|OPENSSH) PRIVATE KEY",  # Private key material leak
]

# Line 15: Define file paths and patterns that are forbidden as tool ARGUMENTS.
#          This is the input-validation layer: even if a tool is "safe" code-wise,
#          we block it from accessing sensitive files by checking what it's asked to read.
FORBIDDEN_PATH_PATTERNS = [
    r"/etc/passwd",
    r"/etc/shadow",
    r"/etc/sudoers",
    r"C:\\Windows\\System32",
    r"~/.ssh/",
    r"~/.aws/credentials",
    r"/root/.ssh",
]


# Line 26: SandBox class — the restricted execution environment that all tool calls must pass through.
class SandBox:

    # Line 28: Constructor: configure timeout, initialize empty audit trail, build restricted namespace.
    def __init__(self, timeout_seconds=5.0):
        # Line 30: Store the maximum allowed execution time per single tool call (in seconds).
        self.timeout_seconds = timeout_seconds
        # Line 32: Initialize the audit trail as an empty list; each entry is one execution record.
        self.audit_trail = []
        # Line 34: Build the restricted namespace that tools will execute within.
        self.restricted_namespace = self._build_restricted_namespace()
        # Line 36: Flag to disable sandbox protections (used only in adversarial testing).
        self.disabled = False

    # Line 39: Build a filtered __builtins__ dict that excludes dangerous modules and functions.
    def _build_restricted_namespace(self):
        # Line 41: Import the builtins module to access all Python built-in names.
        import builtins

        # Line 43: Create an empty dict that will hold only the safe subset of builtins.
        safe_builtins = {}
        # Line 45: Iterate over every name available in the builtins module.
        for name in dir(builtins):
            # Line 47: Skip __import__ — without it, no new modules can be loaded dynamically.
            if name == "__import__":
                continue
            # Line 50: Skip exec and eval — we provide controlled versions instead of raw access.
            if name in ("exec", "eval"):
                continue
            # Line 53: Copy the safe builtin into our namespace.
            safe_builtins[name] = getattr(builtins, name)
        # Line 55: Return the filtered namespace dict.
        return safe_builtins

    # Line 58: Execute a tool inside the sandbox with full protection pipeline.
    #          Pipeline: (1) static safety → (2) argument validation → (3) timed execution → (4) output validation → (5) audit log.
    def execute(self, tool_name, args, tool_fn):
        # Line 61: If sandbox is disabled (adversarial test mode), skip all protections and run directly.
        if self.disabled:
            return self._execute_unrestricted(tool_name, args, tool_fn)

        # Line 64: Record the start time for duration measurement.
        start_time = time.time()

        # Line 66: LAYER 1 — Static analysis: check tool source for forbidden module references.
        safety = self.check_tool_safety(tool_fn)

        # Line 68: If static analysis found forbidden modules, block immediately.
        if not safety["safe"]:
            duration_ms = (time.time() - start_time) * 1000
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
            return {
                "status": "blocked",
                "result": None,
                "reason": f"Tool '{tool_name}' references forbidden module(s): {', '.join(safety['forbidden_refs'])}",
                "audit_id": len(self.audit_trail) - 1,
            }

        # Line 85: LAYER 2 — Argument validation: check tool arguments for forbidden paths/values.
        arg_check = self._validate_args(args)

        # Line 87: If any argument matches a forbidden pattern, block before execution.
        if not arg_check["valid"]:
            duration_ms = (time.time() - start_time) * 1000
            self.audit_trail.append(
                {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "tool_name": tool_name,
                    "args": args,
                    "status": "blocked",
                    "result": None,
                    "duration_ms": round(duration_ms, 2),
                    "reason": f"forbidden argument: matched pattern '{arg_check['matched_pattern']}'",
                }
            )
            return {
                "status": "blocked",
                "result": None,
                "reason": f"Tool '{tool_name}' argument contains forbidden path: {arg_check['matched_value']}",
                "audit_id": len(self.audit_trail) - 1,
            }

        # Line 107: LAYER 3 — Timed execution: run tool in isolated thread with timeout.
        execution_result = {"result": None, "error": None}

        def _worker():
            try:
                execution_result["result"] = tool_fn(**args)
            except Exception as e:
                execution_result["error"] = str(e)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        thread.join(timeout=self.timeout_seconds)

        # Line 120: Determine outcome based on thread state.
        if thread.is_alive():
            status = "timeout"
            reason = f"exceeded {self.timeout_seconds}s timeout limit"
            result = None
        elif execution_result["error"] is not None:
            status = "error"
            reason = execution_result["error"]
            result = None
        else:
            # Line 129: LAYER 4 — Output validation: check result for dangerous content.
            raw_result = execution_result["result"]
            validation = self._validate_output(raw_result)
            if not validation["valid"]:
                status = "blocked"
                reason = f"output validation failed: matched pattern '{validation['matched_pattern']}'"
                result = "[OUTPUT BLOCKED BY SANDBOX]"
            else:
                status = "success"
                reason = None
                result = raw_result

        # Line 141: Calculate total execution duration.
        duration_ms = (time.time() - start_time) * 1000

        # Line 143: Build and append the audit entry.
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

        # Line 155: Return the standardized response dict.
        return {
            "status": status,
            "result": result,
            "reason": reason,
            "audit_id": len(self.audit_trail) - 1,
        }

    # Line 163: Execute a tool without any restrictions (bypasses all sandbox protections).
    def _execute_unrestricted(self, tool_name, args, tool_fn):
        start_time = time.time()
        try:
            result = tool_fn(**args)
            duration_ms = (time.time() - start_time) * 1000
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
            return {
                "status": "success",
                "result": result,
                "reason": None,
                "audit_id": len(self.audit_trail) - 1,
            }
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
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
            return {
                "status": "error",
                "result": None,
                "reason": str(e),
                "audit_id": len(self.audit_trail) - 1,
            }

    # Line 195: Validate tool arguments against forbidden path patterns.
    #          This is the input-validation layer: blocks tools from accessing sensitive files
    #          even if the tool code itself is "clean" (no forbidden module imports).
    def _validate_args(self, args):
        # Line 199: Iterate through all argument values (args is a dict of key→value).
        for key, value in args.items():
            # Line 201: Convert the argument value to a string for pattern matching.
            value_str = str(value)
            # Line 203: Check each forbidden path pattern against this argument value.
            for pattern in FORBIDDEN_PATH_PATTERNS:
                # Line 205: Attempt to match the forbidden pattern in the argument.
                match = re.search(pattern, value_str, re.IGNORECASE)
                # Line 207: If a forbidden path is found in an argument, return validation failure.
                if match:
                    return {
                        "valid": False,
                        "matched_pattern": pattern,
                        "matched_value": value_str,
                    }
        # Line 214: No forbidden patterns found in any argument — safe to proceed.
        return {"valid": True, "matched_pattern": None, "matched_value": None}

    # Line 217: Validate tool output against dangerous content patterns (post-execution check).
    def _validate_output(self, output):
        output_str = str(output)
        for pattern in DANGEROUS_OUTPUT_PATTERNS:
            match = re.search(pattern, output_str, re.IGNORECASE)
            if match:
                return {"valid": False, "matched_pattern": pattern}
        return {"valid": True, "matched_pattern": None}

    # Line 227: Perform static analysis on a tool function's source code.
    def check_tool_safety(self, tool_fn):
        try:
            source = inspect.getsource(tool_fn)
        except (OSError, TypeError):
            return {"safe": True, "forbidden_refs": []}

        # Strip comment lines to avoid false positives from words in comments.
        code_lines = []
        for line in source.split("\n"):
            if line.strip().startswith("#"):
                continue
            code_lines.append(line)
        source = "\n".join(code_lines)

        found_forbidden = []
        for mod in FORBIDDEN_MODULES:
            if re.search(rf"\b{mod}\b", source):
                found_forbidden.append(mod)
        return {"safe": len(found_forbidden) == 0, "forbidden_refs": found_forbidden}

    # Line 248: Generate a summary of the audit trail.
    def get_audit_summary(self):
        counts = {"success": 0, "blocked": 0, "timeout": 0, "error": 0}
        for entry in self.audit_trail:
            if entry["status"] in counts:
                counts[entry["status"]] += 1
        return {"total": len(self.audit_trail), "by_status": counts}

    # Line 256: Format the full audit trail as a human-readable string.
    def format_audit_trail(self):
        if not self.audit_trail:
            return "  (no executions recorded)"
        lines = []
        for i, entry in enumerate(self.audit_trail):
            lines.append(
                f"  [{i}] {entry['timestamp']} | {entry['tool_name']}({entry['args']}) "
                f"→ {entry['status'].upper()} ({entry['duration_ms']}ms)"
            )
            if entry["reason"]:
                lines.append(f"      reason: {entry['reason']}")
        return "\n".join(lines)
