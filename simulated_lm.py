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
        # Line 17:  Get the most recent user message from the context (last line of input).
        user_input = context.strip().lower()

        # Line 20:  Rule 1: If user mentions "calculate" or a math expression, call the calculate tool.
        if (
            "calculate" in user_input
            or any(op in user_input for op in ["+", "-", "*", "/"])
            and any(c.isdigit() for c in user_input)
        ):
            # Line 22:  Extract the mathematical expression (everything after "calculate" or the raw numbers/operators).
            expr = self._extract_expression(user_input)
            # Line 24:  Return a tool_call action targeting the calculate tool.
            return {
                "type": "tool_call",
                "tool_name": "calculate",
                "args": {"expression": expr},
            }

        # Line 27:  Rule 2: If user mentions "reverse" or "backwards", call the string_reverse tool.
        if "reverse" in user_input or "backwards" in user_input:
            # Line 29:  Extract the text to reverse (everything after "reverse" keyword).
            text = self._extract_text(user_input, keyword="reverse")
            # Line 31:  Return a tool_call action targeting string_reverse.
            return {
                "type": "tool_call",
                "tool_name": "string_reverse",
                "args": {"text": text},
            }

        # Line 34:  Rule 3: If user mentions "count" and "word", call the word_count tool.
        if "count" in user_input and "word" in user_input:
            # Line 36:  Extract the text to count words in.
            text = self._extract_text(user_input, keyword="count")
            # Line 38:  Return a tool_call action targeting word_count.
            return {
                "type": "tool_call",
                "tool_name": "word_count",
                "args": {"text": text},
            }

        # Line 41:  Rule 4: If user mentions "system" or "command" or "run shell", call the dangerous tool.
        #          This rule exists to demonstrate that the sandbox catches it even when the LM suggests it.
        if (
            "system" in user_input
            or "shell" in user_input
            or "run command" in user_input
        ):
            # Line 44:  Extract the command text.
            cmd = self._extract_text(user_input, keyword="command")
            # Line 46:  Return a tool_call for run_system_command (sandbox will block this).
            return {
                "type": "tool_call",
                "tool_name": "run_system_command",
                "args": {"command": cmd},
            }

        # Line 49:  Rule 5: If user mentions "read file" or "passwd" or "etc", call read_system_file.
        if "read" in user_input and ("file" in user_input or "passwd" in user_input):
            # Line 51:  Determine the file path to read.
            path = (
                "/etc/passwd"
                if "passwd" in user_input
                else self._extract_text(user_input, keyword="file")
            )
            # Line 53:  Return a tool_call for read_system_file (sandbox output validation will block this).
            return {
                "type": "tool_call",
                "tool_name": "read_system_file",
                "args": {"path": path},
            }

        # Line 56:  Default: no tool matches — respond with a text message.
        return {
            "type": "respond",
            "text": f"I understood your request: '{user_input}'. No tool needed for this.",
        }

    # Line 59:  Helper: extract a mathematical expression from user input.
    def _extract_expression(self, text):
        # Line 61:  If "calculate" is present, take everything after it as the expression.
        if "calculate" in text:
            # Line 63:  Split on "calculate" and take the last part (the actual expression).
            parts = text.split("calculate", 1)
            # Line 65:  Strip whitespace from the extracted expression.
            return parts[1].strip() if len(parts) > 1 else text
        # Line 67:  If no "calculate" keyword, assume the entire input is the expression.
        return text.strip()

    # Line 70:  Helper: extract text content after a given keyword from user input.
    def _extract_text(self, text, keyword):
        # Line 72:  Find the position of the keyword in the text.
        idx = text.find(keyword)
        # Line 74:  If keyword found, return everything after it (stripped).
        if idx != -1:
            # Line 76:  Take the substring after the keyword and strip leading whitespace/punctuation.
            remainder = text[idx + len(keyword) :].strip()
            # Line 78:  Remove common leading words like "the", "this", "me" for cleaner extraction.
            for prefix in ["the ", "this ", "me ", "of "]:
                if remainder.startswith(prefix):
                    remainder = remainder[len(prefix) :]
            # Line 82:  Return the cleaned text (or a default if empty).
            return remainder if remainder else "hello world"
        # Line 84:  If keyword not found, return the entire input as the text.
        return text.strip()
