import sys, json, re

def apply_auto_tags(tools, rules_file):
    with open(rules_file) as f:
        rules = json.load(f)
    for t in tools:
        if "other" in t.get("tags", []):
            for rule in rules:
                if re.match(rule["pattern"], t.get("package", "")):
                    new_tags = [tag for tag in t["tags"] if tag != "other"]
                    new_tags.append(rule["tag"])
                    t["tags"] = sorted(set(new_tags))
                    t["auto_tag_source"] = rule["pattern"]
                    break
    return tools

if __name__ == "__main__":
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file
    rules_file = sys.argv[3] if len(sys.argv) > 3 else "auto_tag_rules.json"
    tools = []
    with open(input_file) as f:
        for line in f:
            tools.append(json.loads(line))
    tools = apply_auto_tags(tools, rules_file)
    with open(output_file, "w") as f:
        for t in tools:
            f.write(json.dumps(t) + "\n")