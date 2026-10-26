# Line 1:  Import the SandBox class (the core new component of this module).
from sandbox import SandBox

# Line 2:  Import the tool registry and individual tools.
from tools import TOOL_REGISTRY, SAFE_TOOLS, DANGEROUS_TOOLS

# Line 3:  Import the SimulatedLM (our stand-in for a real language model).
from simulated_lm import SimulatedLM

# Line 4:  Import the AgentHarness (the loop that ties everything together).
from harness import AgentHarness

# Line 5:  Import the TraceLogger for colored execution reporting.
from trace_logger import TraceLogger


# Line 7:  Main function: wire up all components and run a series of demo scenarios.
def main():
    # Line 9:  Print a header identifying this module.
    print("=" * 60)
    # Line 10:  Print the module title.
    print("  TOYAGENTS MODULE #8: ToySandBox")
    # Line 11:  Print the one-line description.
    print("  Isolated tool execution + audit logging")
    # Line 12:  Print a separator.
    print("=" * 60)

    # Line 15:  Create the SandBox with a 3-second timeout (short for demo purposes).
    sandbox = SandBox(timeout_seconds=3.0)

    # Line 17:  Create the SimulatedLM instance (the "brain").
    lm = SimulatedLM()

    # Line 19:  Create the AgentHarness, wiring up LM + sandbox + tools + guardrails.
    harness = AgentHarness(
        lm=lm,
        sandbox=sandbox,
        tool_registry=TOOL_REGISTRY,
        max_iterations=5,
        max_input_length=500,
    )

    # Line 28:  Create a TraceLogger to collect and display execution traces.
    logger = TraceLogger()

    # Line 30:  Define the demo scenarios to run (each tests a different sandbox behavior).
    scenarios = [
        ("Calculate 12 + 7", "Safe tool: basic arithmetic"),
        ("Reverse hello world", "Safe tool: string manipulation"),
        ("Count words in this sentence please", "Safe tool: word counting"),
        (
            "Run command dir",
            "DANGEROUS: os.system reference → sandbox blocks via static analysis",
        ),
        (
            "Read file /etc/passwd",
            "DANGEROUS: output validation → sandbox blocks dangerous output",
        ),
    ]

    # Line 39:  Print a blank line before the scenarios.
    print()

    # Line 41:  Iterate through each demo scenario.
    for i, (user_input, description) in enumerate(scenarios):
        # Line 43:  Print the scenario number and description.
        print(f"\n{'─' * 50}")
        # Line 45:  Print the scenario label.
        print(f"  Scenario {i+1}: {description}")
        # Line 47:  Print the user input that will be sent to the agent.
        print(f'  Input: "{user_input}"')
        # Line 49:  Print a separator before the execution trace.
        print(f"{'─' * 50}")

        # Line 51:  Clear the harness trace events for this run (fresh trace per scenario).
        harness.trace_events = []

        # Line 53:  Run the agent with this user input.
        result = harness.run(user_input)

        # Line 55:  Copy the harness events into the logger for rendering.
        for event in harness.trace_events:
            # Line 57:  Log each event to the trace logger.
            logger.log(event["component"], event["message"], event.get("detail"))

        # Line 60:  Render the colored trace report for this scenario.
        logger.report()

        # Line 62:  Clear the logger events so the next scenario starts fresh.
        logger.events = []

        # Line 64:  Print the agent's final response.
        print(f"\n  Agent Response: {result['response']}")
        # Line 66:  Print metadata (iterations used).
        print(f"  Iterations: {result['iterations']}")

    # Line 69:  Print a summary section.
    print(f"\n\n{'═' * 60}")
    # Line 71:  Print the audit trail summary header.
    print("  AUDIT TRAIL SUMMARY")
    # Line 72:  Print separator.
    print(f"{'═' * 60}")

    # Line 74:  Get the audit summary from the sandbox.
    summary = sandbox.get_audit_summary()
    # Line 76:  Print total executions.
    print(f"  Total tool executions: {summary['total']}")
    # Line 78:  Print breakdown by status.
    for status, count in summary["by_status"].items():
        # Line 80:  Format each status line with a visual indicator.
        icon = "✓" if status == "success" else "✗"
        print(f"    {icon} {status:>8}: {count}")

    # Line 84:  Print the full audit trail in detail.
    print(f"\n  Full Audit Trail:")
    # Line 86:  Get the formatted audit trail string from the sandbox.
    print(sandbox.format_audit_trail())

    # Line 88:  Print a closing message about the key insight.
    print(f"\n{'═' * 60}")
    # Line 90:  Print the key takeaway.
    print("  KEY INSIGHT: The sandbox adds 3 layers of protection:")
    # Line 92:  Layer 1 description.
    print("    1. STATIC ANALYSIS — blocks tools that reference forbidden modules")
    # Line 94:  Layer 2 description.
    print("    2. TIMEOUT — kills tools that run too long (thread join with timeout)")
    # Line 96:  Layer 3 description.
    print("    3. OUTPUT VALIDATION — blocks results containing dangerous patterns")
    # Line 98:  Print the production analogy.
    print("  In production, this is Docker/WASM/VMs. Same concept, bigger cage.")
    # Line 100:  Print closing separator.
    print(f"{'═' * 60}")


# Line 103:  Entry point guard: only run main() when executed directly (not when imported).
if __name__ == "__main__":
    # Line 105:  Call the main function to start the demo.
    main()
