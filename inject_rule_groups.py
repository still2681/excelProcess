"""Inject rule_groups metadata into config JSON files."""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))

RULE_GROUP_TEMPLATES = {
    "data": {"label": "数据质量", "rules": ["data.quality"]},
    "country": {"label": "国家", "rules": ["country.whitelist"]},
    "email": {
        "label": "邮箱",
        "rules": [
            "email.numeric_local",
            "email.free_provider",
            "email.country_tld",
            "email.publisher",
            "email.generic_tld",
            "email.student",
            "email.pharma_biotech",
            "email.academic_special",
        ],
    },
    "aff.commercial": {
        "label": "机构 - 商业剔除",
        "rules": [
            "aff.commercial_suffix",
            "aff.commercial_keyword",
            "aff.named_company",
        ],
    },
    "aff.china": {
        "label": "机构 - 中国专项",
        "rules": ["aff.cn_non_elite", "aff.cn_hospital"],
    },
    "name": {"label": "姓名", "rules": ["name.india_surname"]},
}

RULE_GROUP_ORDER = ["data", "country", "email", "aff.commercial", "aff.china", "name"]


def inject_rule_groups(config):
    rule_ids = {rule["id"] for rule in config.get("rules", [])}
    rule_groups = {}
    for group_id, group_info in RULE_GROUP_TEMPLATES.items():
        rules = [rid for rid in group_info["rules"] if rid in rule_ids]
        if rules:
            rule_groups[group_id] = {"label": group_info["label"], "rules": rules}
    config["rule_groups"] = rule_groups
    config["rule_group_order"] = [gid for gid in RULE_GROUP_ORDER if gid in rule_groups]
    return config


def main():
    paths = [
        os.path.join(BASE, "config", "package.json"),
        os.path.join(BASE, "package-simple.json"),
    ]
    for path in paths:
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
        inject_rule_groups(config)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"Updated {path}")


if __name__ == "__main__":
    main()
