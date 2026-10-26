# Line 1:  No external imports needed — this is a pure keyword-matching rule engine.


# Line 3:  SimulatedLM class: mimics an LLM's decision-making using simple keyword matching.
#          In production, this would be replaced by a real API call to GPT/Claude/etc.
#          The key insight: the harness doesn't care WHAT is behind generate() — it just calls it.
class SimulatedLM:

    # Line 7:  Constructor: no configuration needed for this simple rule-based simulator.
    def __init__(self):
        # Line 9:  Store a call counter to track how many times the LM has been invoked (for debugging).
        self.call_count = 0

    # Line 12:  Generate the next action based on the conversation context.
    #          Returns a dict with "type" (either "tool_call" or "respond") and relevant fields.
    def generate(self, context):
        # Line 15:  Increment the call counter each time generate() is invoked.
        self.call_count += 1
        # Line 17:  Get the full context as a lowercase string for keyword matching.
        user_input = context.strip().lower()

        # Line 20:  PRIORITY RULE: If the context already contains a tool result, respond with it.
        #          This mimics real LM behavior: once you have the answer from a tool, you summarize it.
        #          Without this rule, the LM would keep re-calling tools with polluted context.
        if (
            "[tool result]" in user_input
            or "[tool blocked]" in user_input
            or "[tool error]" in user_input
            or "[tool timeout]" in user_input
        ):
            # Line 24:  Extract the relevant tool outcome from the context for the response.
            outcome = self._extract_outcome(user_input)
            # Line 26:  Return a final response that acknowledges the tool's result (or block/error).
            return {"type": "respond", "text": outcome}

        # Line 29:  Rule 1: If user mentions "calculate" or a math expression, call the calculate tool.
        if "calculate" in user_input or (
            any(op in user_input for op in ["+", "-", "*", "/"])
            and any(c.isdigit() for c in user_input)
        ):
            # Line 31:  Extract the mathematical expression (first line only, to avoid context pollution).
            expr = self._extract_expression(user_input)
            # Line 33:  Return a tool_call action targeting the calculate tool.
            return {
                "type": "tool_call",
                "tool_name": "calculate",
                "args": {"expression": expr},
            }

        # Line 36:  Rule 2: If user mentions "reverse" or "backwards", call the string_reverse tool.
        if "reverse" in user_input or "backwards" in user_input:
            # Line 38:  Extract the text to reverse (first line only).
            text = self._extract_text(user_input, keyword="reverse")
            # Line 40:  Return a tool_call action targeting string_reverse.
            return {
                "type": "tool_call",
                "tool_name": "string_reverse",
                "args": {"text": text},
            }

        # Line 43:  Rule 3: If user mentions "count" and "word", call the word_count tool.
        if "count" in user_input and "word" in user_input:
            # Line 45:  Extract the text to count words in (first line only).
            text = self._extract_text(user_input, keyword="count")
            # Line 47:  Return a tool_call action targeting word_count.
            return {
                "type": "tool_call",
                "tool_name": "word_count",
                "args": {"text": text},
            }

        # Line 50:  Rule 4: If user mentions "system" or "command" or "run shell", call the dangerous tool.
        #          This rule exists to demonstrate that the sandbox catches it even when the LM suggests it.
        if (
            "system" in user_input
            or "shell" in user_input
            or "run command" in user_input
        ):
            # Line 53:  Extract the command text (first line only).
            cmd = self._extract_text(user_input, keyword="command")
            # Line 55:  Return a tool_call for run_system_command (sandbox will block this).
            return {
                "type": "tool_call",
                "tool_name": "run_system_command",
                "args": {"command": cmd},
            }

        # Line 58:  Rule 5: If user mentions "read file" or "passwd" or "etc", call read_system_file.
        if "read" in user_input and ("file" in user_input or "passwd" in user_input):
            # Line 60:  Determine the file path to read.
            path = (
                "/etc/passwd"
                if "passwd" in user_input
                else self._extract_text(user_input, keyword="file")
            )
            # Line 62:  Return a tool_call for read_system_file (sandbox output validation will block this).
            return {
                "type": "tool_call",
                "tool_name": "read_system_file",
                "args": {"path": path},
            }

        # Line 65:  Default: no tool matches — respond with a text message.
        return {
            "type": "respond",
            "text": f"I understood your request: '{user_input}'. No tool needed for this.",
        }

    # Line 68:  Helper: extract the tool outcome from context for use in a final response.
    def _extract_outcome(self, context):
        # Line 70:  If a tool was blocked, report that to the user concisely.
        if "[tool blocked]" in context:
            # Line 72:  Find the block marker and extract everything after it.
            idx = context.find("[tool blocked]")
            raw = context[idx + len("[tool blocked]") :].strip()
            # Line 75:  Strip the redundant "X was blocked by sandbox:" prefix added by the harness,
            #          keeping only the core technical reason (e.g., "Tool 'os' references forbidden module(s): os").
            if "was blocked by sandbox:" in raw:
                core_reason = raw.split("was blocked by sandbox:", 1)[1].strip()
            else:
                core_reason = raw
            # Line 80:  Return a single clean sentence (no repeated "blocked" phrasing).
            return (
                f"Sandbox security check prevented this action. Reason: {core_reason}"
            )

        # Line 83:  If a tool timed out, report that concisely.
        if "[tool timeout]" in context:
            # Line 85:  Find and extract the timeout reason.
            idx = context.find("[tool timeout]")
            raw = context[idx + len("[tool timeout]") :].strip()
            # Line 88:  Strip redundant prefix if present.
            if "exceeded" in raw:
                core_reason = raw.split(":", 1)[1].strip() if ":" in raw else raw
            else:
                core_reason = raw
            # Line 93:  Return a concise timeout message.
            return f"The tool exceeded its time limit and was stopped. Detail: {core_reason}"

        # Line 96:  If a tool errored, report that concisely.
        if "[tool error]" in context:
            # Line 98:  Find and extract the error message.
            idx = context.find("[tool error]")
            raw = context[idx + len("[tool error]") :].strip()
            # Line 101:  Strip redundant prefix if present.
            if "failed:" in raw:
                core_reason = raw.split("failed:", 1)[1].strip()
            else:
                core_reason = raw
            # Line 106:  Return a concise error message.
            return f"The tool encountered an error. Detail: {core_reason}"

        # Line 109:  If a tool succeeded, present its result.
        if "[tool result]" in context:
            # Line 111:  Find and extract the result text.
            idx = context.find("[tool result]")
            raw = context[idx + len("[tool result]") :].strip()
            # Line 114:  Strip the "X returned:" prefix to get just the value.
            if " returned:" in raw:
                core_result = raw.split(" returned:", 1)[1].strip()
            else:
                core_result = raw
            # Line 119:  Return a clean result presentation.
            return f"Result: {core_result}"

        # Line 122:  Fallback (should not reach here given the guard in generate()).
        return "I processed your request."

    # Line 109:  Helper: extract a mathematical expression from user input.
    def _extract_expression(self, text):
        # Line 111:  If "calculate" is present, take everything after it as the expression candidate.
        if "calculate" in text:
            # Line 113:  Split on "calculate" and take the part after the first occurrence.
            parts = text.split("calculate", 1)
            # Line 115:  Take only the FIRST LINE of the remainder (prevents context pollution from appended tool results).
            remainder = (
                parts[1].strip().split("\n")[0].strip() if len(parts) > 1 else text
            )
        # Line 118:  If no "calculate" keyword, assume the entire first line is the expression.
        else:
            # Line 120:  Take only the first line (safety against multi-line context).
            remainder = text.strip().split("\n")[0].strip()
        # Line 123:  Return the extracted expression (first line only, clean of system markers).
        return remainder

    # Line 126:  Helper: extract text content after a given keyword from user input.
    def _extract_text(self, text, keyword):
        # Line 128:  Find the position of the keyword in the text.
        idx = text.find(keyword)
        # Line 130:  If keyword found, return everything after it (first line only).
        if idx != -1:
            # Line 132:  Take the substring after the keyword, but ONLY the first line (prevents context pollution).
            remainder = text[idx + len(keyword) :].strip().split("\n")[0].strip()
            # Line 134:  Remove common leading words like "the", "this", "me" for cleaner extraction.
            for prefix in ["the ", "this ", "me ", "of "]:
                if remainder.startswith(prefix):
                    remainder = remainder[len(prefix) :]
            # Line 138:  Return the cleaned text (or a default if empty).
            return remainder if remainder else "hello world"
        # Line 140:  If keyword not found, return the entire first line as the text.
        return text.strip().split("\n")[0].strip()
