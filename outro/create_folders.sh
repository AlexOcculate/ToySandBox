#!/bin/bash

# chmod +x screate_folders.sh

touch main.py               # Entry point: wires everything together
touch sandbox.py            # SandBox class (restricted namespace, timeout, audit trail)
touch tools.py              # Tool definitions (safe tools + one dangerous tool for testing)
touch simulated_lm.py       # SimulatedLM with keyword rules
touch harness.py            # Agent loop (routes all tool calls through SandBox)
touch trace_logger.py       # ANSI colored trace logger (sandbox-specific colors)
touch test_adversarial.py   # 5 adversarial tests proving sandbox resilience
touch README.md