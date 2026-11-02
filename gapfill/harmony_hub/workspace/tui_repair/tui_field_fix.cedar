# CEDARscript patch: Make build_tree_str resilient to field name variations.
# Adds import and pre-processing step without altering the rest of the file.

ADD_IMPORT at line 25:
```
from harmony_hub.workspace.tui_repair.message_adapter import normalize_messages
```

MODIFY FUNCTION build_tree_str at line 71:
  Insert after "def build_tree_str(messages, ...):" and docstring, before "msg_map = {}":
```
    messages = normalize_messages(messages)
```