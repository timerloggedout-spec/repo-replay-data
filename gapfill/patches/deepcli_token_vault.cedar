# CEDARdiff patch to replace get_token() with vault call
diff --git a/core.py b/core.py
--- a/deepcli/core.py
+++ b/deepcli/core.py
@@ ... @@
-def get_token():
-    # old: reads upload-api.json and returns raw token
-    import json
-    with open('/data/data/com.termux/files/home/deepseek-cli/upload-api.json') as f:
-        data = json.load(f)
-    return data['authorization']
+import sys, os
+sys.path.insert(0, os.path.expanduser("~/workspace/cedar_forge/vault"))
+from secure_token import get_token as _secure_get_token
+
+def get_token():
+    return _secure_get_token()