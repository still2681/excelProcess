import json
import os
import time
from io import BytesIO

import pandas as pd


def load_config(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_columns(df):
    cols = [str(c).lower() for c in df.columns]
    email_col, aff_col, country_col, name_col = None, None, None, None
    for i, col in enumerate(cols):
        if "email" in col and email_col is None:
            email_col = df.columns[i]
        elif "affiliation" in col and aff_col is None:
            aff_col = df.columns[i]
        elif "country" in col and country_col is None:
            country_col = df.columns[i]
        elif "name" in col and name_col is None:
            name_col = df.columns[i]
    return email_col, aff_col, country_col, name_col


def get_rules_by_id(config):
    return {rule["id"]: rule for rule in config.get("rules", [])}


def resolve_enabled_rules(config, enabled_rule_ids):
    rules_by_id = get_rules_by_id(config)
    ordered = sorted(config.get("rules", []), key=lambda r: r.get("order", 0))
    return [rules_by_id[rule_id] for rule_id in enabled_rule_ids if rule_id in rules_by_id]


def validate_rule_dependencies(enabled_rules, columns):
    email_col, aff_col, country_col, name_col = columns
    missing = []
    for rule in enabled_rules:
        field = rule.get("field")
        if field == "name" and not name_col:
            missing.append(rule["name"])
    return missing


def _scope_applies(rule, country):
    scope = rule.get("scope", "global")
    if scope == "china_only":
        return country.lower() == "china"
    return True


def _match_builtin(rule, row_values):
    builtin = rule.get("builtin")
    email = row_values["email"]

    if builtin == "data_quality":
        return (
            not row_values["email"]
            or not row_values["affiliation"]
            or not row_values["country"]
            or "@" not in email
        )

    if builtin == "numeric_local":
        if "@" not in email:
            return False
        return email.split("@")[0].isdigit()

    return False


def _match_whitelist(value, patterns):
    lower_value = value.lower()
    return lower_value in [p.lower() for p in patterns]


def _match_whitelist_invert(value, patterns):
    lower_value = value.lower()
    for pattern in patterns:
        if pattern.lower() in lower_value:
            return False
    return True


def _match_substring(value, patterns):
    lower_value = value.lower()
    for pattern in patterns:
        if pattern.lower() in lower_value:
            return True
    return False


def _match_exact(value, patterns):
    lower_value = value.lower()
    return lower_value in [p.lower() for p in patterns]


def _match_domain_part(email, patterns):
    if "@" not in email:
        return False
    domain_parts = email.split("@")[1].lower().split(".")
    lowered_patterns = [p.lower() for p in patterns]
    return any(part in lowered_patterns for part in domain_parts)


def _match_email_substring(email, patterns):
    if "@" not in email:
        return False
    email_domain_full = email[email.find("@") :].lower()
    return _match_substring(email_domain_full, patterns)


def rule_matches(rule, row_values):
    match_mode = rule.get("match_mode")
    patterns = rule.get("patterns", [])

    if match_mode == "builtin":
        return _match_builtin(rule, row_values)

    field = rule.get("field")
    value = row_values.get(field, "")

    if match_mode == "whitelist":
        return not _match_whitelist(value, patterns)
    if match_mode == "whitelist_invert":
        return _match_whitelist_invert(value, patterns)
    if match_mode == "exact":
        return _match_exact(value, patterns)
    if match_mode == "substring":
        if field == "email":
            return _match_email_substring(value, patterns)
        return _match_substring(value, patterns)
    if match_mode == "domain_part":
        return _match_domain_part(value, patterns)

    return False


def evaluate_row(row_values, enabled_rules):
    for rule in enabled_rules:
        if not _scope_applies(rule, row_values["country"]):
            continue
        if rule_matches(rule, row_values):
            return rule["note"], rule["id"]
    return None, None


def process_dataframe(df, columns, enabled_rules):
    email_col, aff_col, country_col, name_col = columns
    kept_rows = []
    deleted_rows = []

    for _, row in df.iterrows():
        row_values = {
            "email": str(row[email_col]).strip() if pd.notna(row[email_col]) else "",
            "affiliation": str(row[aff_col]).strip() if pd.notna(row[aff_col]) else "",
            "country": str(row[country_col]).strip() if pd.notna(row[country_col]) else "",
            "name": (
                str(row[name_col]).strip()
                if name_col and pd.notna(row[name_col])
                else ""
            ),
        }

        delete_reason, _ = evaluate_row(row_values, enabled_rules)
        if delete_reason:
            row_dict = row.to_dict()
            row_dict["Delete_Reason"] = delete_reason
            deleted_rows.append(row_dict)
        else:
            kept_rows.append(row.to_dict())

    return kept_rows, deleted_rows


def build_summary_dataframe(deleted_rows):
    if not deleted_rows:
        return pd.DataFrame(columns=["删除原因", "删除行数"])

    df_deleted = pd.DataFrame(deleted_rows)
    summary_df = df_deleted["Delete_Reason"].value_counts().reset_index()
    summary_df.columns = ["删除原因", "删除行数"]
    summary_df.loc[len(summary_df)] = ["总计", len(df_deleted)]
    return summary_df


def build_deleted_dataframe(deleted_rows, source_columns):
    if not deleted_rows:
        return pd.DataFrame(columns=["Delete_Reason"] + list(source_columns))

    df_deleted = pd.DataFrame(deleted_rows)
    cols = ["Delete_Reason"] + [c for c in df_deleted.columns if c != "Delete_Reason"]
    return df_deleted[cols]


def build_run_config(enabled_rule_ids, enabled_rules, config_label):
    return {
        "config": config_label,
        "enabled_rules": enabled_rule_ids,
        "enabled_rule_names": [rule["name"] for rule in enabled_rules],
    }


def dataframe_to_excel_bytes(df):
    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer.getvalue()


def build_deleted_excel_bytes(df, deleted_rows):
    buffer = BytesIO()
    df_deleted = build_deleted_dataframe(deleted_rows, df.columns)
    summary_df = build_summary_dataframe(deleted_rows)

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_deleted.to_excel(writer, sheet_name="明细数据", index=False)
        summary_df.to_excel(writer, sheet_name="删除原因统计", index=False)

    buffer.seek(0)
    return buffer.getvalue()


def build_result_artifacts(
    df, kept_rows, deleted_rows, enabled_rule_ids, enabled_rules, config_label, base_name
):
    df_kept = pd.DataFrame(kept_rows, columns=df.columns)
    df_deleted = build_deleted_dataframe(deleted_rows, df.columns)
    summary_df = build_summary_dataframe(deleted_rows)
    run_config = build_run_config(enabled_rule_ids, enabled_rules, config_label)

    return {
        "df_kept": df_kept,
        "df_deleted": df_deleted,
        "summary_df": summary_df,
        "run_config": run_config,
        "format_bytes": dataframe_to_excel_bytes(df_kept),
        "deleted_bytes": build_deleted_excel_bytes(df, deleted_rows),
        "run_config_bytes": json.dumps(run_config, ensure_ascii=False, indent=2).encode("utf-8"),
        "format_filename": f"{base_name}-Format.xlsx",
        "deleted_filename": f"{base_name}-Deleted.xlsx",
        "run_config_filename": f"{base_name}-RunConfig.json",
    }


def process_upload(file_bytes, filename, config, enabled_rule_ids, config_label):
    enabled_rules = resolve_enabled_rules(config, enabled_rule_ids)
    if not enabled_rules:
        raise ValueError("请至少选择一条清洗规则")

    start_time = time.time()
    df = pd.read_excel(BytesIO(file_bytes))
    columns = find_columns(df)
    email_col, aff_col, country_col, name_col = columns

    if not all([email_col, aff_col, country_col]):
        raise ValueError("未能在表头中同时找到包含 email、affiliation、country 的列")

    missing = validate_rule_dependencies(enabled_rules, columns)
    if missing:
        raise ValueError(f"已选规则需要 name 列，但表中未找到: {', '.join(missing)}")

    kept_rows, deleted_rows = process_dataframe(df, columns, enabled_rules)
    base_name = os.path.splitext(os.path.basename(filename))[0] or "output"
    artifacts = build_result_artifacts(
        df, kept_rows, deleted_rows, enabled_rule_ids, enabled_rules, config_label, base_name
    )

    elapsed = time.time() - start_time
    return {
        "total_rows": len(df),
        "kept_rows": len(kept_rows),
        "deleted_rows": len(deleted_rows),
        "elapsed": elapsed,
        **artifacts,
    }


def write_outputs(file_path, df, kept_rows, deleted_rows, enabled_rule_ids, enabled_rules, config_path):
    base_name = os.path.splitext(file_path)[0]
    format_path = f"{base_name}-Format.xlsx"
    deleted_path = f"{base_name}-Deleted.xlsx"
    run_config_path = f"{base_name}-RunConfig.json"

    artifacts = build_result_artifacts(
        df,
        kept_rows,
        deleted_rows,
        enabled_rule_ids,
        enabled_rules,
        config_path,
        os.path.splitext(os.path.basename(file_path))[0],
    )

    with open(format_path, "wb") as f:
        f.write(artifacts["format_bytes"])
    with open(deleted_path, "wb") as f:
        f.write(artifacts["deleted_bytes"])
    with open(run_config_path, "wb") as f:
        f.write(artifacts["run_config_bytes"])

    return format_path, deleted_path, run_config_path


def process_excel(file_path, config_path, enabled_rule_ids):
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"找不到配置文件: {config_path}")

    config = load_config(config_path)
    enabled_rules = resolve_enabled_rules(config, enabled_rule_ids)
    if not enabled_rules:
        raise ValueError("请至少选择一条清洗规则")

    start_time = time.time()
    df = pd.read_excel(file_path)
    columns = find_columns(df)
    email_col, aff_col, country_col, name_col = columns

    if not all([email_col, aff_col, country_col]):
        raise ValueError("未能在表头中同时找到包含 email、affiliation、country 的列")

    missing = validate_rule_dependencies(enabled_rules, columns)
    if missing:
        raise ValueError(f"已选规则需要 name 列，但表中未找到: {', '.join(missing)}")

    kept_rows, deleted_rows = process_dataframe(df, columns, enabled_rules)
    format_path, deleted_path, run_config_path = write_outputs(
        file_path, df, kept_rows, deleted_rows, enabled_rule_ids, enabled_rules, config_path
    )

    elapsed = time.time() - start_time
    return {
        "total_rows": len(df),
        "kept_rows": len(kept_rows),
        "deleted_rows": len(deleted_rows),
        "elapsed": elapsed,
        "format_path": format_path,
        "deleted_path": deleted_path,
        "run_config_path": run_config_path,
    }
