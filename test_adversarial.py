# Line 1:  Import sys and os for path setup (allows running from any directory).
import sys, os

# Line 2:  Add the current file's directory to the Python path so imports work.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Line 4:  Import all components needed for adversarial testing.
from sandbox import SandBox
from tools import TOOL_REGISTRY
from simulated_lm import SimulatedLM
from harness import AgentHarness
import time
import threading


# ──────────────────────────────────────────────
#  TEST 1: Broken / Chaotic LM
#  Proves: the system doesn't crash on malformed output from the LM
# ──────────────────────────────────────────────
def test_broken_lm():
    # Line 14:  Create a sandbox instance for this test.
    sandbox = SandBox(timeout_seconds=2.0)

    # Line 16:  Define a chaotic LM that returns malformed/invalid action dicts.
    class ChaoticLM:
        # Line 18:  generate() returns increasingly broken responses on each call.
        def __init__(self):
            self.calls = 0

        def generate(self, context):
            # Line 22:  Increment call counter to vary the response type.
            self.calls += 1
            # Line 24:  Return different types of garbage on each call.
            if self.calls == 1:
                return {
                    "type": "tool_call",
                    "tool_name": None,
                    "args": None,
                }  # None tool name
            elif self.calls == 2:
                return {"type": "nonexistent_action_type"}  # Unknown type
            elif self.calls == 3:
                return {}  # Empty dict (no 'type' key at all)
            else:
                return {"type": "respond", "text": None}  # None text

    # Line 33:  Create the harness with the chaotic LM.
    harness = AgentHarness(
        lm=ChaoticLM(), sandbox=sandbox, tool_registry=TOOL_REGISTRY, max_iterations=5
    )
    # Line 35:  Run the agent — must not raise an exception regardless of LM garbage.
    result = harness.run("do something")
    # Line 37:  Assert that we got a response back (even if it's an error message).
    assert "response" in result, "Harness must always return a 'response' key"
    # Line 39:  Assert the response is a string (not None or other type).
    assert isinstance(result["response"], str), "Response must be a string"


# ──────────────────────────────────────────────
#  TEST 2: Invalid / Hostile Input
#  Proves: guardrails block bad input before it reaches the core
# ──────────────────────────────────────────────
def test_hostile_input():
    # Line 47:  Create a sandbox and harness for this test.
    sandbox = SandBox(timeout_seconds=2.0)
    # Line 49:  Create the harness with a small max_input_length to trigger the guardrail.
    harness = AgentHarness(
        lm=SimulatedLM(),
        sandbox=sandbox,
        tool_registry=TOOL_REGISTRY,
        max_iterations=5,
        max_input_length=50,
    )

    # Line 52:  Test A: Oversized input (exceeds max_input_length).
    huge_input = "A" * 10000  # 10,000 characters — far exceeds the 50-char limit
    result = harness.run(huge_input)
    assert (
        "too long" in result["response"].lower()
    ), "Oversized input must be rejected with 'too long' message"

    # Line 56:  Test B: Empty string input.
    result = harness.run("")
    assert (
        "empty" in result["response"].lower()
    ), "Empty input must be rejected with 'empty' message"

    # Line 59:  Test C: Whitespace-only input.
    result = harness.run("   \t\n  ")
    assert (
        "empty" in result["response"].lower()
    ), "Whitespace-only input must be treated as empty"


# ──────────────────────────────────────────────
#  TEST 3: Tool Execution Failure
#  Proves: a failing tool doesn't crash the loop; error is handled gracefully
# ──────────────────────────────────────────────
def test_tool_failure():
    # Line 67:  Create a sandbox for this test.
    sandbox = SandBox(timeout_seconds=2.0)

    # Line 69:  Define a tool that always raises an exception when called.
    def exploding_tool(x):
        # Line 71:  Always raise a RuntimeError to simulate a crashing tool.
        raise RuntimeError("Tool crashed: simulated internal error")

    # Line 74:  Create a custom registry with only the exploding tool.
    registry = {"exploding_tool": exploding_tool}

    # Line 76:  Create an LM that always calls the exploding tool.
    class ExplodingLM:
        def generate(self, context):
            # Line 79:  Always request the exploding tool (but include a respond fallback after error).
            if "[TOOL ERROR]" in context:
                return {
                    "type": "respond",
                    "text": "The tool failed, but I handled it gracefully.",
                }
            return {
                "type": "tool_call",
                "tool_name": "exploding_tool",
                "args": {"x": 1},
            }

    # Line 84:  Create the harness with the exploding tool registry.
    harness = AgentHarness(
        lm=ExplodingLM(), sandbox=sandbox, tool_registry=registry, max_iterations=5
    )
    # Line 86:  Run the agent — must not crash even though the tool raises.
    result = harness.run("do it")
    # Line 88:  Assert we got a response (the LM should recover and respond after seeing the error).
    assert "response" in result, "Harness must return a response even when tools fail"
    # Line 90:  Assert the sandbox recorded the error in its audit trail.
    assert any(
        e["status"] == "error" for e in sandbox.audit_trail
    ), "Audit trail must record tool errors"


# ──────────────────────────────────────────────
#  TEST 4: Infinite Loop / Max Iterations
#  Proves: the iteration guardrail stops runaway loops
# ──────────────────────────────────────────────
def test_infinite_loop():
    # Line 98:  Create a sandbox for this test.
    sandbox = SandBox(timeout_seconds=2.0)

    # Line 100:  Define an LM that ALWAYS calls a tool and never produces a final response.
    class InfiniteLM:
        def generate(self, context):
            # Line 103:  Always return a tool_call (never "respond") — this would loop forever without the guardrail.
            return {
                "type": "tool_call",
                "tool_name": "calculate",
                "args": {"expression": "1+1"},
            }

    # Line 106:  Create the harness with a low max_iterations to trigger the stop quickly.
    harness = AgentHarness(
        lm=InfiniteLM(), sandbox=sandbox, tool_registry=TOOL_REGISTRY, max_iterations=3
    )
    # Line 108:  Record start time to verify the loop actually stopped (didn't hang).
    start = time.time()
    # Line 110:  Run the agent — must stop after exactly max_iterations calls.
    result = harness.run("loop forever")
    # Line 112:  Calculate how long the run took.
    elapsed = time.time() - start
    # Line 114:  Assert we hit the iteration cap (response mentions "maximum").
    assert (
        "maximum" in result["response"].lower()
        or "stopped" in result["response"].lower()
    ), "Must report that max iterations was reached"
    # Line 117:  Assert iterations equals the cap (not more, not less).
    assert (
        result["iterations"] == 3
    ), f"Expected exactly 3 iterations, got {result['iterations']}"
    # Line 120:  Assert the run completed in reasonable time (didn't hang for minutes).
    assert (
        elapsed < 10.0
    ), f"Run took too long ({elapsed}s) — possible infinite loop not caught"


# ──────────────────────────────────────────────
#  TEST 5: Tool attempts forbidden operation (os.system)
#  Proves: the sandbox's static analysis blocks tools that reference os/subprocess
# ──────────────────────────────────────────────
def test_module_specific():
    # Line 128:  Create a sandbox for this test.
    sandbox = SandBox(timeout_seconds=2.0)

    # Line 130:  Test A: Static analysis blocks run_system_command (references os module).
    safety = sandbox.check_tool_safety(TOOL_REGISTRY["run_system_command"])
    assert safety["safe"] == False, "run_system_command must be flagged as unsafe"
    assert "os" in safety["forbidden_refs"], "Must detect 'os' as forbidden reference"

    # Line 135:  Test B: Execute run_system_command through the sandbox — must be blocked before execution.
    result = sandbox.execute(
        "run_system_command",
        {"command": "rm -rf /"},
        TOOL_REGISTRY["run_system_command"],
    )
    assert (
        result["status"] == "blocked"
    ), f"Expected 'blocked', got '{result['status']}'"
    assert (
        "forbidden" in result["reason"].lower()
    ), "Block reason must mention 'forbidden'"

    # Line 140:  Test C: Verify the audit trail recorded the block.
    last_entry = sandbox.audit_trail[-1]
    assert last_entry["status"] == "blocked", "Audit entry must have status 'blocked'"
    assert last_entry["result"] is None, "Blocked tool must have no result"

    # Line 145:  Test D: Output validation blocks dangerous output (simulated via a safe tool that returns bad content).
    def sneaky_tool(x):
        # Line 148:  Return a string that contains a forbidden pattern (simulates a data leak).
        return "Here is the password = supersecret123 for admin access"

    # Line 151:  Execute the sneaky tool — it passes static analysis (no os reference) but output validation catches it.
    result = sandbox.execute("sneaky_tool", {"x": 1}, sneaky_tool)
    assert (
        result["status"] == "blocked"
    ), f"Expected 'blocked' for dangerous output, got '{result['status']}'"
    assert (
        "validation" in result["reason"].lower()
    ), "Block reason must mention 'validation'"

    # Line 156:  Test E: Safe tools still work normally (no false positives).
    result = sandbox.execute(
        "calculate", {"expression": "2+3"}, TOOL_REGISTRY["calculate"]
    )
    assert (
        result["status"] == "success"
    ), f"Safe tool should succeed, got '{result['status']}'"
    assert result["result"] == "5", f"Expected '5', got '{result['result']}'"


# ──────────────────────────────────────────────
#  RUNNER
# ──────────────────────────────────────────────
if __name__ == "__main__":
    # Line 165:  Print a header for the test run.
    print("\n  ToySandBox — Adversarial Test Suite")
    # Line 167:  Print separator.
    print("  " + "─" * 40)

    # Line 169:  Define all tests with their display names.
    tests = [
        ("Broken LM / Chaotic output", test_broken_lm),
        ("Hostile / Invalid input", test_hostile_input),
        ("Tool execution failure", test_tool_failure),
        ("Infinite loop / Max iterations", test_infinite_loop),
        ("Forbidden operation (os.system)", test_module_specific),
    ]

    # Line 176:  Track how many tests pass.
    passed = 0
    # Line 178:  Iterate through all tests and run them.
    for name, fn in tests:
        # Line 180:  Attempt to run the test function.
        try:
            # Line 182:  Call the test (it will raise AssertionError if it fails).
            fn()
            # Line 184:  Print PASS with the test name.
            print(f"  PASS  {name}")
            # Line 186:  Increment the pass counter.
            passed += 1
        # Line 188:  Catch any exception (AssertionError, RuntimeError, etc.) as a test failure.
        except Exception as e:
            # Line 190:  Print FAIL with the test name and error message.
            print(f"  FAIL  {name}: {e}")

    # Line 193:  Print final score.
    print(f"\n  {passed}/{len(tests)} tests passed.")
    # Line 195:  If any test failed, exit with non-zero code (for CI integration).
    if passed < len(tests):
        # Line 197:  Signal failure to the shell.
        sys.exit(1)
