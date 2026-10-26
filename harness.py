# Line 1:  Import time for measuring total agent execution duration.
import time


# Line 3:  AgentHarness class: the main loop that orchestrates LM → tool_call → sandbox → response.
#          This is structurally identical to Module #0's harness, EXCEPT that all tool executions
#          are routed through SandBox.execute() instead of being called directly.
class AgentHarness:

    # Line 7:  Constructor: wire up the LM, sandbox, tool registry, and guardrail parameters.
    def __init__(
        self, lm, sandbox, tool_registry, max_iterations=5, max_input_length=1000
    ):
        # Line 9:  Store the language model (the "brain" — swappable without changing harness).
        self.lm = lm
        # Line 11:  Store the sandbox instance (the "cage" that restricts tool execution).
        self.sandbox = sandbox
        # Line 13:  Store the tool registry (dict mapping tool names to function objects).
        self.tool_registry = tool_registry
        # Line 15:  Maximum number of LM→tool iterations before forcing a stop (prevents infinite loops).
        self.max_iterations = max_iterations
        # Line 17:  Maximum allowed input length (guardrail against oversized/malicious inputs).
        self.max_input_length = max_input_length
        # Line 19:  List to store all trace events for the trace logger.
        self.trace_events = []

    # Line 22:  Log an event to the internal trace list (called throughout the loop for observability).
    def _log(self, component, message, detail=None):
        # Line 24:  Append the event with a timestamp for chronological ordering.
        self.trace_events.append(
            {
                "time": time.strftime("%H:%M:%S"),
                "component": component,
                "message": message,
                "detail": detail,
            }
        )

    # Line 32:  Main entry point: process a user input and return the agent's final response.
    def run(self, user_input):
        # Line 34:  Record the start time for total duration measurement.
        start_time = time.time()

        # Line 36:  GUARDRAIL 1: Check input length (block oversized inputs before they reach the LM).
        if len(user_input) > self.max_input_length:
            # Line 38:  Log the guardrail block event.
            self._log(
                "guardrails",
                f"Input BLOCKED: length {len(user_input)} exceeds max {self.max_input_length}",
            )
            # Line 40:  Return an error response immediately without entering the loop.
            return {
                "response": f"Error: input too long ({len(user_input)} chars). Max allowed: {self.max_input_length}.",
                "iterations": 0,
            }

        # Line 43:  GUARDRAIL 2: Check for empty or whitespace-only input.
        if not user_input.strip():
            # Line 45:  Log the empty input rejection.
            self._log("guardrails", "Input BLOCKED: empty or whitespace-only")
            # Line 47:  Return an error response for empty input.
            return {"response": "Error: input is empty.", "iterations": 0}

        # Line 50:  Log the start of a new agent run.
        self._log(
            "loop",
            f"Agent run started | input: '{user_input[:60]}{'...' if len(user_input) > 60 else ''}'",
        )

        # Line 52:  Initialize the conversation context with the user's input.
        context = user_input

        # Line 54:  Initialize iteration counter (tracks how many LM calls we've made).
        iterations = 0

        # Line 56:  ENTER THE AGENT LOOP: keep calling the LM until it produces a final response or we hit the cap.
        while iterations < self.max_iterations:
            # Line 58:  Increment iteration counter at the start of each loop pass.
            iterations += 1
            # Line 60:  Log that we're entering a new iteration.
            self._log("loop", f"Iteration {iterations}/{self.max_iterations}")

            # Line 62:  CALL THE LM: ask it what to do given the current context.
            action = self.lm.generate(context)
            # Line 64:  Log the LM's decision (what type of action it chose).
            self._log("lm", f"Decision: {action['type']}", detail=str(action))

            # Line 67:  CASE 1: LM decided to respond directly (no tool needed) — this ends the loop.
            if action["type"] == "respond":
                # Line 69:  Log the final response.
                self._log("lm", f"Final response: '{action['text'][:80]}'")
                # Line 71:  Calculate total duration and return the response.
                duration = (time.time() - start_time) * 1000
                # Line 73:  Return the final response with metadata.
                return {
                    "response": action["text"],
                    "iterations": iterations,
                    "duration_ms": round(duration, 2),
                }

            # Line 76:  CASE 2: LM decided to call a tool — route it through the sandbox.
            if action["type"] == "tool_call":
                # Line 78:  Extract the tool name from the LM's action.
                tool_name = action.get("tool_name", "")
                # Line 80:  Extract the arguments dict from the LM's action.
                args = action.get("args", {})

                # Line 82:  GUARDRAIL 3: Verify the tool exists in our registry (block unknown tools).
                if tool_name not in self.tool_registry:
                    # Line 84:  Log that an unknown tool was requested.
                    self._log(
                        "guardrails", f"Tool BLOCKED: '{tool_name}' not in registry"
                    )
                    # Line 86:  Feed the error back to the LM as context so it can try again or respond.
                    context = f"{context}\n[SYSTEM] Error: tool '{tool_name}' does not exist. Available tools: {list(self.tool_registry.keys())}. Please respond directly."
                    # Line 88:  Continue to next iteration (LM gets another chance).
                    continue

                # Line 91:  Get the actual function object from the registry.
                tool_fn = self.tool_registry[tool_name]

                # Line 93:  Log that we're about to execute a tool through the sandbox.
                self._log(
                    "sandbox",
                    f"Executing: {tool_name}({args})",
                    detail="routing through SandBox.execute()",
                )

                # Line 95:  EXECUTE THE TOOL THROUGH THE SANDBOX (this is the key difference from Module #0).
                exec_result = self.sandbox.execute(tool_name, args, tool_fn)

                # Line 97:  Log the sandbox execution result with its status.
                self._log(
                    "sandbox",
                    f"Result: {exec_result['status'].upper()}",
                    detail=exec_result.get("reason"),
                )

                # Line 99:  Feed the execution result back into the context so the LM can use it in its next decision.
                if exec_result["status"] == "success":
                    # Line 101:  Tool succeeded — append the result to context.
                    context = f"{context}\n[TOOL RESULT] {tool_name} returned: {exec_result['result']}"
                elif exec_result["status"] == "blocked":
                    # Line 104:  Tool was blocked by sandbox — inform the LM so it can explain to user.
                    context = f"{context}\n[TOOL BLOCKED] {tool_name} was blocked by sandbox: {exec_result['reason']}"
                elif exec_result["status"] == "timeout":
                    # Line 107:  Tool timed out — inform the LM of the timeout.
                    context = f"{context}\n[TOOL TIMEOUT] {tool_name} exceeded time limit: {exec_result['reason']}"
                else:
                    # Line 110:  Tool errored — inform the LM of the error.
                    context = f"{context}\n[TOOL ERROR] {tool_name} failed: {exec_result['reason']}"

                # Line 113:  Continue to next iteration (LM will see the result and decide what to do next).
                continue

            # Line 116:  CASE 3: Unknown action type from LM (defensive programming — should never happen with SimulatedLM).
            self._log(
                "lm",
                f"Unknown action type: '{action.get('type')}' — treating as respond",
            )
            # Line 118:  Fall back to a generic response.
            duration = (time.time() - start_time) * 1000
            return {
                "response": "I'm not sure how to handle that.",
                "iterations": iterations,
                "duration_ms": round(duration, 2),
            }

        # Line 122:  EXIT CONDITION: max_iterations reached without a final response.
        self._log("loop", f"STOPPED: max iterations ({self.max_iterations}) reached")
        # Line 124:  Calculate total duration for the forced stop.
        duration = (time.time() - start_time) * 1000
        # Line 126:  Return a timeout/stop message to the user.
        return {
            "response": f"Stopped: reached maximum of {self.max_iterations} iterations without a final answer.",
            "iterations": iterations,
            "duration_ms": round(duration, 2),
        }
