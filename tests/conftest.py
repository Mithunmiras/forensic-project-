import os

# Tests must not call the network; LLM paths are tested with a stub in test_llm.py.
os.environ["FORENSIC_DISABLE_LLM"] = "1"
