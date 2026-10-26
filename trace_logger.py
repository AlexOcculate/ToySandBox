# Line 1:  No external imports — ANSI escape codes are raw strings (work in all modern terminals).


# Line 3:  Define ANSI color codes as constants for reuse throughout the logger.
class Colors:
    # Line 5:  Reset code to return terminal to default colors after each styled segment.
    RESET = "\033[0m"
    # Line 7:  Bold text for headers and emphasis.
    BOLD = "\033[1m"
    # Line 9:  Component colors (each major component gets a unique color for visual scanning).
    LOOP = "\033[92m"  # Bright green — the main agent loop
    LM = "\033[96m"  # Bright cyan — the language model decisions
    SANDBOX = "\033[95m"  # Bright magenta — sandbox execution (the star of this module)
    GUARDRAILS = "\033[91m"  # Bright red — guardrail blocks and rejections
    TOOLS = "\033[93m"  # Bright yellow — tool invocations
    AUDIT = "\033[37m"  # White — audit trail entries
    # Line 17:  Status detail colors (background + foreground combos for high visibility).
    SUCCESS_BG = "\033[42;30m"  # Green background + black text — success
    BLOCKED_BG = "\033[41;97m"  # Red background + white text — blocked/denied
    ERROR_BG = "\033[43;30m"  # Yellow background + black text — error/timeout
    INFO_BG = "\033[44;97m"  # Blue background + white text — informational


# Line 25:  TraceLogger class: collects events during execution and renders a colored report.
class TraceLogger:

    # Line 27:  Constructor: initialize an empty event list.
    def __init__(self):
        # Line 29:  Store all logged events in order of occurrence.
        self.events = []

    # Line 32:  Log a single event with component, message, and optional detail.
    def log(self, component, message, detail=None):
        # Line 34:  Append the event to our internal list for later rendering.
        self.events.append(
            {"component": component, "message": message, "detail": detail}
        )

    # Line 37:  Get the appropriate ANSI color code for a given component name.
    def _get_color(self, component):
        # Line 39:  Map component names to their assigned colors.
        color_map = {
            "loop": Colors.LOOP,
            "lm": Colors.LM,
            "sandbox": Colors.SANDBOX,
            "guardrails": Colors.GUARDRAILS,
            "tools": Colors.TOOLS,
            "audit": Colors.AUDIT,
        }
        # Line 48:  Return the color for this component, or default to reset if unknown.
        return color_map.get(component, Colors.RESET)

    # Line 51:  Get the appropriate background color for a status detail string.
    def _get_status_color(self, detail):
        # Line 53:  If detail contains "BLOCKED" or "blocked", use red background.
        if detail and ("BLOCKED" in detail or "blocked" in detail.lower()):
            return Colors.BLOCKED_BG
        # Line 56:  If detail contains "timeout" or "error", use yellow background.
        if detail and (
            "timeout" in detail.lower()
            or "error" in detail.lower()
            or "failed" in detail.lower()
        ):
            return Colors.ERROR_BG
        # Line 59:  Default: no special background (use foreground only).
        return None

    # Line 62:  Render the full trace report to stdout with colors and formatting.
    def report(self):
        # Line 64:  Print a header line for the trace section.
        print(f"\n{Colors.BOLD}{'═' * 60}{Colors.RESET}")
        # Line 66:  Print the trace title.
        print(f"{Colors.BOLD}  TRACE REPORT — ToySandBox Agent Execution{Colors.RESET}")
        # Line 68:  Print a separator line under the header.
        print(f"{Colors.BOLD}{'═' * 60}{Colors.RESET}")

        # Line 70:  If no events were logged, print a message and return early.
        if not self.events:
            # Line 72:  Indicate that nothing was traced.
            print("  (no events recorded)")
            # Line 74:  End the report.
            return

        # Line 76:  Iterate through all events and render each one with appropriate coloring.
        for i, event in enumerate(self.events):
            # Line 78:  Get the color for this event's component.
            comp_color = self._get_color(event["component"])
            # Line 80:  Format the component tag in its assigned color (e.g., "[SANDBOX]").
            comp_tag = f"{comp_color}[{event['component'].upper():>10}]{Colors.RESET}"
            # Line 82:  Print the main line: index, component tag, and message.
            print(f"  {i+1:>3}. {comp_tag} {event['message']}")

            # Line 84:  If there's a detail string, render it with status-appropriate coloring.
            if event["detail"]:
                # Line 86:  Check if the detail warrants a background color (blocked/error/timeout).
                status_color = self._get_status_color(event["detail"])
                # Line 88:  If a status color applies, wrap the detail in that background.
                if status_color:
                    # Line 90:  Print the detail with colored background for high visibility.
                    print(f"        {status_color}  {event['detail']}{Colors.RESET}")
                else:
                    # Line 93:  Otherwise, print the detail as plain indented text.
                    print(f"        → {event['detail']}")

        # Line 96:  Print a closing separator line.
        print(f"{Colors.BOLD}{'═' * 60}{Colors.RESET}")
