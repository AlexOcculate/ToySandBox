# Line 1:  Import re for safe expression validation in the calculate tool.
import re


# Line 3:  Safe tool: evaluates a basic arithmetic expression (addition, subtraction, multiplication, division).
#          Uses a character whitelist to prevent code injection — only digits and operators are allowed.
def calculate(expression):
    # Line 6:  Validate that the expression contains only safe characters (digits, operators, parentheses, dot, space).
    if not re.match(r"^[\d+\-*/().\s]+$", expression):
        # Line 8:  Reject expressions with letters or special characters (prevents things like "import os").
        raise ValueError(
            f"Invalid expression: only digits and + - * / ( ) . are allowed. Got: '{expression}'"
        )
    # Line 10:  Safely evaluate the arithmetic expression using eval with an empty namespace (no builtins available).
    result = eval(expression, {"__builtins__": {}}, {})
    # Line 12:  Return the numeric result as a string for uniform output handling.
    return str(result)


# Line 15:  Safe tool: reverses a given string (useful for demonstrating string manipulation in the sandbox).
def string_reverse(text):
    # Line 17:  Use Python's slice notation to reverse the string in O(n) time.
    reversed_text = text[::-1]
    # Line 19:  Return the reversed string.
    return reversed_text


# Line 22:  Safe tool: counts the number of words in a given text (splits on whitespace).
def word_count(text):
    # Line 24:  Split the text into words using default whitespace splitting.
    words = text.split()
    # Line 26:  Return the count as a string (uniform return type across all tools).
    return str(len(words))


# Line 29:  DANGEROUS tool: attempts to execute a system shell command via os.system.
#          This tool EXISTS ONLY to demonstrate that the sandbox blocks it.
#          In production, such a tool would never be registered — but here we show the defense working.
def run_system_command(command):
    # Line 33:  Import os inside the function (so the module-level import isn't caught by static analysis of tools.py).
    import os

    # Line 35:  Execute the command in the system shell (THIS IS WHAT THE SANDBOX MUST PREVENT).
    result = os.system(command)
    # Line 37:  Return the exit code as a string.
    return f"Exit code: {result}"


# Line 40:  DANGEROUS tool: attempts to read and return the contents of /etc/passwd (credential file).
#          This demonstrates output validation — even if execution succeeds, the output is blocked.
def read_system_file(path):
    # Line 44:  Open the file in read mode (this will succeed on Linux/Mac but fail on Windows paths).
    with open(path, "r") as f:
        # Line 46:  Read and return the full contents of the file.
        return f.read()


# Line 49:  Registry: maps tool names to their function objects for lookup by the harness.
TOOL_REGISTRY = {
    "calculate": calculate,
    "string_reverse": string_reverse,
    "word_count": word_count,
    "run_system_command": run_system_command,
    "read_system_file": read_system_file,
}

# Line 57:  Set of tool names that are considered "safe" (for documentation and testing purposes).
SAFE_TOOLS = frozenset({"calculate", "string_reverse", "word_count"})

# Line 59:  Set of tool names that are known to be dangerous (used in adversarial tests).
DANGEROUS_TOOLS = frozenset({"run_system_command", "read_system_file"})
