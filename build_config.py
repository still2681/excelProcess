"""One-off helper: convert legacy rule JSON to layered config format."""
import json
import os

SUFFIX_PATTERNS = [
    " Ltd.", " Ltd,", " Ltd ", " Co.", " Corp.", " Inc.", " Inc,", " Inc ",
    " LLC", " GmbH", " S.A.", " N.V.", " Plc", " Pty", " Limited", " limited",
]
KEYWORD_PATTERNS = [" Company", " Industry"]
NAMED_COMPANY_PATTERNS = [
    "Bruker", "ProLynx", "Merck", "danone", "Bristol Myers Squibb",
    "FasCure Therapeut", "Medimmune", "Novimmune", "ImmunoGenes",
    "Bionor Immuno", "Heat Biologics",
]
FREE_EMAIL_PATTERNS = ["hotmail", "yahoo", "126", "sohu", "qq", "aol"]
PUBLISHER_PATTERNS = ["wiley", "elsevier", "springer", "doaj", "mdpi"]
GENERIC_TLD_PATTERNS = ["net", "org", "mil"]

GROUP_LABELS = {
    "data": "数据质量",
    "country": "国家",
    "email": "邮箱",
    "affiliation": "机构",
    "name": "姓名",
}


def get_list(rule_dict):
    raw = rule_dict.get("list", {})
    if isinstance(raw, dict):
        return list(raw.values())
    if isinstance(raw, list):
        return raw
    return []


def split_commercial_pub(full_list):
    known = set(FREE_EMAIL_PATTERNS + PUBLISHER_PATTERNS + GENERIC_TLD_PATTERNS)
    country_tld = [p for p in full_list if p not in known]
    free = [p for p in full_list if p in FREE_EMAIL_PATTERNS]
    publisher = [p for p in full_list if p in PUBLISHER_PATTERNS]
    generic = [p for p in full_list if p in GENERIC_TLD_PATTERNS]
    return free, country_tld, publisher, generic


def build_rules(legacy, simple=False):
    email_rules = legacy.get("email_rules", {})
    aff_rules = legacy.get("affiliation_rules", {})
    country_rules = legacy.get("country_rules", {})
    name_rules = legacy.get("name_rules", {})

    pharma = email_rules.get("pharma_biotech", {})
    commercial_pub = email_rules.get("commercial_pub", {})
    student = email_rules.get("student_email", {})
    academic = email_rules.get("Academic_email", {})
    commercial_aff = aff_rules.get("commercial_aff", {})
    cn_hosp = aff_rules.get("CN_hosp", {})
    cn_save = aff_rules.get("CN_aff_save", {})
    country_save = country_rules.get("country_save", {})
    india_name = name_rules.get("india_name", {})

    free_list, tld_list, pub_list, generic_list = split_commercial_pub(get_list(commercial_pub))

    rules = [
        {
            "id": "data.quality",
            "group": "data",
            "level": 0,
            "name": "空值与邮箱格式",
            "note": "数据缺失或邮箱格式错误(缺少@)",
            "scope": "global",
            "match_mode": "builtin",
            "builtin": "data_quality",
            "default_enabled": True,
        },
        {
            "id": "email.numeric_local",
            "group": "email",
            "level": 1,
            "name": "全数字邮箱",
            "note": "全数字邮箱",
            "scope": "global",
            "match_mode": "builtin",
            "builtin": "numeric_local",
            "default_enabled": False,
        },
        {
            "id": "name.india_surname",
            "group": "name",
            "level": 1,
            "name": "印度常见姓氏",
            "note": india_name.get("note", "印度姓氏"),
            "scope": "global",
            "field": "name",
            "match_mode": "exact",
            "patterns": get_list(india_name),
            "default_enabled": False,
        },
        {
            "id": "country.whitelist",
            "group": "country",
            "level": 1,
            "name": "国家白名单",
            "note": country_save.get("note", "country-非优质国家"),
            "scope": "global",
            "field": "country",
            "match_mode": "whitelist",
            "patterns": get_list(country_save),
            "default_enabled": True,
        },
        {
            "id": "email.free_provider",
            "group": "email",
            "level": 1,
            "name": "免费/个人邮箱",
            "note": "email-免费/个人邮箱",
            "scope": "global",
            "field": "email",
            "match_mode": "domain_part",
            "patterns": free_list,
            "default_enabled": True,
        },
        {
            "id": "email.country_tld",
            "group": "email",
            "level": 2,
            "name": "邮箱域名含特定国家TLD",
            "note": "email-域名含特定国家TLD",
            "scope": "global",
            "field": "email",
            "match_mode": "domain_part",
            "patterns": tld_list,
            "default_enabled": True,
        },
        {
            "id": "email.publisher",
            "group": "email",
            "level": 2,
            "name": "出版社邮箱",
            "note": "email-出版社",
            "scope": "global",
            "field": "email",
            "match_mode": "domain_part",
            "patterns": pub_list,
            "default_enabled": True,
        },
        {
            "id": "email.generic_tld",
            "group": "email",
            "level": 2,
            "name": "通用域名后缀(net/org/mil)",
            "note": "email-通用域名后缀",
            "scope": "global",
            "field": "email",
            "match_mode": "domain_part",
            "patterns": generic_list,
            "default_enabled": True,
        },
        {
            "id": "email.student",
            "group": "email",
            "level": 1,
            "name": "学生邮箱",
            "note": student.get("note", "email-学生邮箱"),
            "scope": "global",
            "field": "email",
            "match_mode": "substring",
            "patterns": get_list(student),
            "default_enabled": True,
        },
        {
            "id": "email.pharma_biotech",
            "group": "email",
            "level": 3,
            "name": "制药/生物技术公司邮箱",
            "note": pharma.get("note", "email-制药生物技术"),
            "scope": "global",
            "field": "email",
            "match_mode": "domain_part",
            "patterns": get_list(pharma),
            "default_enabled": True,
        },
        {
            "id": "email.academic_special",
            "group": "email",
            "level": 3,
            "name": "特定学术邮箱",
            "note": academic.get("note", "email-中科院文献情报中心"),
            "scope": "global",
            "field": "email",
            "match_mode": "substring",
            "patterns": get_list(academic),
            "default_enabled": True,
        },
    ]

    if simple:
        suffix_patterns = [
            p for p in SUFFIX_PATTERNS + KEYWORD_PATTERNS
            if p in get_list(commercial_aff) or p.strip() in [x.strip() for x in get_list(commercial_aff)]
        ]
        if not suffix_patterns:
            suffix_patterns = SUFFIX_PATTERNS + KEYWORD_PATTERNS
        named_patterns = []
    else:
        suffix_patterns = SUFFIX_PATTERNS
        keyword_patterns = KEYWORD_PATTERNS
        named_patterns = NAMED_COMPANY_PATTERNS
        rules.extend([
            {
                "id": "aff.commercial_keyword",
                "group": "affiliation",
                "level": 2,
                "name": "机构含商业关键词",
                "note": "affiliation-含 Company/Industry",
                "scope": "global",
                "field": "affiliation",
                "match_mode": "substring",
                "patterns": keyword_patterns,
                "default_enabled": True,
            },
            {
                "id": "aff.named_company",
                "group": "affiliation",
                "level": 3,
                "name": "已知商业公司名",
                "note": "affiliation-已知商业公司",
                "scope": "global",
                "field": "affiliation",
                "match_mode": "substring",
                "patterns": named_patterns,
                "default_enabled": True,
            },
        ])

    rules.extend([
        {
            "id": "aff.commercial_suffix",
            "group": "affiliation",
            "level": 1,
            "name": "机构含公司法律后缀",
            "note": "affiliation-含 Ltd/Inc/GmbH 等",
            "scope": "global",
            "field": "affiliation",
            "match_mode": "substring",
            "patterns": suffix_patterns if simple else SUFFIX_PATTERNS,
            "default_enabled": True,
        },
        {
            "id": "aff.cn_non_elite",
            "group": "affiliation",
            "level": 3,
            "name": "中国非985/211/双一流机构",
            "note": cn_save.get("note", "affiliation-CN非精英校"),
            "scope": "china_only",
            "field": "affiliation",
            "match_mode": "whitelist_invert",
            "patterns": get_list(cn_save),
            "default_enabled": True,
        },
        {
            "id": "aff.cn_hospital",
            "group": "affiliation",
            "level": 1,
            "name": "中国机构含医院/医学院",
            "note": cn_hosp.get("note", "affiliation-CN医院医学院"),
            "scope": "china_only",
            "field": "affiliation",
            "match_mode": "substring",
            "patterns": get_list(cn_hosp),
            "default_enabled": True,
        },
    ])

    for i, rule in enumerate(rules):
        rule["order"] = i + 1

    all_ids = [r["id"] for r in rules]
    default_ids = [r["id"] for r in rules if r.get("default_enabled")]

    presets = {
        "full_legacy": {
            "label": "完整清洗（等同旧版默认）",
            "rules": default_ids,
        },
        "basic": {
            "label": "基础清洗（仅数据质量+国家）",
            "rules": ["data.quality", "country.whitelist"],
        },
        "light_commercial": {
            "label": "轻度商业剔除",
            "rules": [
                "data.quality", "country.whitelist",
                "email.free_provider", "aff.commercial_suffix",
            ],
        },
        "china_hospital_only": {
            "label": "中国专项-仅医院/医学院",
            "rules": ["data.quality", "country.whitelist", "aff.cn_hospital"],
        },
        "china_elite_only": {
            "label": "中国专项-仅非985/211",
            "rules": ["data.quality", "country.whitelist", "aff.cn_non_elite"],
        },
        "mmailer_india": {
            "label": "MMailer-印度姓氏+全数字邮箱",
            "rules": [
                "data.quality", "email.numeric_local", "name.india_surname",
                "country.whitelist",
            ],
        },
        "custom": {
            "label": "自定义（手动勾选）",
            "rules": [],
        },
    }

    return {
        "group_labels": GROUP_LABELS,
        "presets": presets,
        "rules": rules,
    }


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    legacy_full_path = os.path.join(base, "config", "package.json")
    legacy_simple_path = os.path.join(base, "package-simple.json")

    with open(legacy_full_path, encoding="utf-8") as f:
        legacy_full = json.load(f)
    with open(legacy_simple_path, encoding="utf-8") as f:
        legacy_simple = json.load(f)

    full_config = build_rules(legacy_full, simple=False)
    simple_config = build_rules(legacy_simple, simple=True)

    with open(legacy_full_path, "w", encoding="utf-8") as f:
        json.dump(full_config, f, ensure_ascii=False, indent=2)

    with open(legacy_simple_path, "w", encoding="utf-8") as f:
        json.dump(simple_config, f, ensure_ascii=False, indent=2)

    print("Generated config/package.json and package-simple.json")


if __name__ == "__main__":
    main()
