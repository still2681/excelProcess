import os
import sys
from io import BytesIO

# Ensure repo root is on path (Streamlit Cloud working directory safety)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import pandas as pd
import streamlit as st

from rule_engine import (
    find_matching_preset,
    get_effective_enabled_rule_ids,
    get_rule_action,
    get_rule_group_order,
    get_rule_groups,
    get_rules_by_id,
    load_config,
    process_upload,
    sync_group_selection,
)

CONFIG_PATH = os.path.join(BASE_DIR, "config", "package.json")
CONFIG_LABEL = "完整规则集"
PRESET_STATE_KEY = "active_preset"
GROUP_ORDER = ["data", "country", "email", "affiliation", "name"]

MATCH_MODE_LABELS = {
    "builtin": "内置逻辑",
    "whitelist": "白名单（不在列表中则删除）",
    "whitelist_invert": "反向白名单（不在白名单机构中则删除）",
    "substring": "子串匹配（包含即命中）",
    "domain_part": "邮箱域名分段匹配",
    "exact": "精确匹配",
}

BUILTIN_LABELS = {
    "data_quality": "email、affiliation、country 任一为空，或邮箱不含 @",
    "numeric_local": "邮箱 @ 前的本地部分全部为数字",
}

SCOPE_LABELS = {
    "global": "全球",
    "china_only": "仅 China",
}


ACTION_PREFIX = {
    "delete_on_match": "【删除】",
    "keep_if_match": "【保留】",
}


def format_rule_label(rule):
    prefix = ACTION_PREFIX.get(get_rule_action(rule), "")
    level = rule.get("level", 0)
    return f"{prefix} L{level} {rule['name']}"


def describe_rule_logic(rule):
    action = get_rule_action(rule)
    if action == "keep_if_match":
        if rule.get("match_mode") == "whitelist":
            return "保留规则（全部删除规则之后执行）：国家在允许名单内则保留，否则删除"
        if rule.get("match_mode") == "whitelist_invert":
            return "保留规则（全部删除规则之后执行）：中国机构匹配精英校名单则保留，否则删除"
        return "保留规则（全部删除规则之后执行）"

    match_mode = rule.get("match_mode")
    if match_mode == "builtin":
        return BUILTIN_LABELS.get(rule.get("builtin", ""), "内置规则")

    field = rule.get("field", "")
    mode_label = MATCH_MODE_LABELS.get(match_mode, match_mode)
    scope = SCOPE_LABELS.get(rule.get("scope", "global"), rule.get("scope", "global"))
    return f"作用字段: {field} | 匹配方式: {mode_label} | 范围: {scope}"


def is_rule_effectively_enabled(config, rule_id):
    return rule_id in get_effective_enabled_rule_ids(
        config,
        st.session_state.rule_selection,
        st.session_state.group_selection,
    )


def render_rule_details(config):
    st.subheader("规则详情")
    st.caption("查看每条规则的具体匹配逻辑和完整关键词列表。")

    group_labels = config.get("group_labels", {})
    ui_groups = get_rule_groups(config)
    rules = sorted(config.get("rules", []), key=lambda r: r.get("order", 0))

    filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 2])
    with filter_col1:
        ui_group_labels = ["全部"] + [info["label"] for info in ui_groups.values()]
        ui_group_filter = st.selectbox("规则分组", ui_group_labels)
    with filter_col2:
        scope_filter = st.selectbox("显示范围", ["全部规则", "仅已生效规则"])
    with filter_col3:
        keyword = st.text_input("搜索关键词", placeholder="在国家/邮箱/机构关键词中搜索…")

    if scope_filter == "仅已生效规则":
        rules = [r for r in rules if is_rule_effectively_enabled(config, r["id"])]

    if ui_group_filter != "全部":
        selected_ui_group = next(
            (gid for gid, info in ui_groups.items() if info["label"] == ui_group_filter),
            None,
        )
        if selected_ui_group:
            allowed = set(ui_groups[selected_ui_group]["rules"])
            rules = [r for r in rules if r["id"] in allowed]

    if keyword.strip():
        kw = keyword.strip().lower()
        filtered = []
        for rule in rules:
            haystack = " ".join(
                [
                    rule.get("id", ""),
                    rule.get("name", ""),
                    rule.get("note", ""),
                    describe_rule_logic(rule),
                    " ".join(rule.get("patterns", [])),
                ]
            ).lower()
            if kw in haystack:
                filtered.append(rule)
        rules = filtered

    if not rules:
        st.warning("没有符合条件的规则。")
        return

    st.markdown(f"共 **{len(rules)}** 条规则")

    for rule in rules:
        level = rule.get("level", 0)
        group = group_labels.get(rule.get("group", ""), rule.get("group", ""))
        enabled = is_rule_effectively_enabled(config, rule["id"])
        checked_only = st.session_state.rule_selection.get(rule["id"], False)
        if checked_only and not enabled:
            status = "已勾选但未生效（所属分组已关闭）"
            icon = "⚠️"
        else:
            status = "已生效" if enabled else "未生效"
            icon = "✅" if enabled else "⬜"
        header = f"{icon} {format_rule_label(rule)}（{group}）"

        with st.expander(header, expanded=False):
            st.markdown(f"**规则 ID：** `{rule['id']}`")
            st.markdown(f"**删除原因备注：** {rule.get('note', '')}")
            st.markdown(f"**匹配逻辑：** {describe_rule_logic(rule)}")
            st.caption(f"当前状态：{status}")

            patterns = rule.get("patterns", [])
            if patterns:
                st.markdown(f"**关键词列表（共 {len(patterns)} 项）**")
                if len(patterns) <= 30:
                    st.dataframe(
                        pd.DataFrame({"关键词": patterns}),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    preview = pd.DataFrame({"关键词": patterns[:30]})
                    st.dataframe(preview, use_container_width=True, hide_index=True)
                    st.caption("列表较长，下方可查看全部或复制。")
                    st.text_area(
                        f"全部关键词 - {rule['name']}",
                        value="\n".join(patterns),
                        height=240,
                        disabled=True,
                        label_visibility="collapsed",
                    )
            else:
                st.info("该规则无关键词列表，按上方匹配逻辑自动判断。")

            preset_names = [
                info["label"]
                for info in config.get("presets", {}).values()
                if rule["id"] in info.get("rules", [])
            ]
            if preset_names:
                st.markdown("**包含该规则的预设：** " + "、".join(preset_names))


def init_session_state():
    if "rule_selection" not in st.session_state:
        st.session_state.rule_selection = {}
    if "group_selection" not in st.session_state:
        st.session_state.group_selection = {}
    if "result" not in st.session_state:
        st.session_state.result = None
    if "rules_initialized" not in st.session_state:
        st.session_state.rules_initialized = False


def get_all_preset_ids(config):
    presets = config.get("presets", {})
    return [pid for pid in presets if pid != "custom"] + ["custom"]


def get_preset_label(config, preset_id):
    return config.get("presets", {}).get(preset_id, {}).get("label", preset_id)


def apply_preset(config, preset_id):
    preset_rules = set(config["presets"][preset_id].get("rules", []))
    for rule in config.get("rules", []):
        st.session_state.rule_selection[rule["id"]] = rule["id"] in preset_rules
    st.session_state.group_selection = sync_group_selection(
        config, st.session_state.rule_selection, st.session_state.group_selection
    )


def on_preset_change():
    config = load_config(CONFIG_PATH)
    preset_id = st.session_state[PRESET_STATE_KEY]
    if preset_id != "custom":
        apply_preset(config, preset_id)
        st.session_state.result = None


def ensure_rule_selection(config):
    if not st.session_state.rules_initialized:
        default_preset = "full_legacy" if "full_legacy" in config.get("presets", {}) else get_all_preset_ids(config)[0]
        apply_preset(config, default_preset)
        st.session_state[PRESET_STATE_KEY] = default_preset
        st.session_state.rules_initialized = True
        st.session_state.result = None

    for rule in config.get("rules", []):
        st.session_state.rule_selection.setdefault(rule["id"], rule.get("default_enabled", False))

    st.session_state.group_selection = sync_group_selection(
        config, st.session_state.rule_selection, st.session_state.group_selection
    )

    if PRESET_STATE_KEY not in st.session_state:
        st.session_state[PRESET_STATE_KEY] = find_matching_preset(
            config,
            st.session_state.rule_selection,
            st.session_state.group_selection,
        )


def sync_preset_before_widgets(config):
    """Update preset selectbox state before the widget renders."""
    matching = find_matching_preset(
        config,
        st.session_state.rule_selection,
        st.session_state.group_selection,
    )
    st.session_state[PRESET_STATE_KEY] = matching
    return matching


def request_preset_resync_if_needed(config, previous_matching):
    """After checkbox edits, rerun so preset can sync on the next run."""
    current_matching = find_matching_preset(
        config,
        st.session_state.rule_selection,
        st.session_state.group_selection,
    )
    if current_matching != previous_matching:
        st.rerun()


def load_config_data():
    return load_config(CONFIG_PATH)


def get_enabled_rule_ids(config):
    return get_effective_enabled_rule_ids(
        config,
        st.session_state.rule_selection,
        st.session_state.group_selection,
    )


def render_tree_checkbox(glyph, label, value, disabled=False, nested=False):
    glyph_col, check_col = st.columns([0.14, 0.86], gap="small")
    indent = "&nbsp;&nbsp;&nbsp;&nbsp;" if nested else ""
    with glyph_col:
        st.markdown(
            f"<span style='color:#888;font-family:monospace'>{indent}{glyph}</span>",
            unsafe_allow_html=True,
        )
    with check_col:
        return st.checkbox(label, value=value, disabled=disabled)


def render_grouped_rule_checkboxes(config):
    rules_by_id = get_rules_by_id(config)
    rule_groups = get_rule_groups(config)

    for group_id in get_rule_group_order(config):
        group_info = rule_groups[group_id]
        rule_ids = group_info["rules"]

        if len(rule_ids) == 1:
            rule_id = rule_ids[0]
            rule = rules_by_id[rule_id]
            checked = render_tree_checkbox("•", format_rule_label(rule), st.session_state.rule_selection.get(rule_id, False))
            st.session_state.rule_selection[rule_id] = checked
            st.session_state.group_selection[group_id] = checked
            continue

        group_enabled = render_tree_checkbox("▼", group_info["label"], st.session_state.group_selection.get(group_id, False))
        st.session_state.group_selection[group_id] = group_enabled

        for index, rule_id in enumerate(rule_ids):
            rule = rules_by_id[rule_id]
            branch = "└─" if index == len(rule_ids) - 1 else "├─"
            child_checked = render_tree_checkbox(
                branch,
                format_rule_label(rule),
                st.session_state.rule_selection.get(rule_id, False),
                disabled=not group_enabled,
                nested=True,
            )
            if group_enabled:
                st.session_state.rule_selection[rule_id] = child_checked

        if group_enabled:
            any_child = any(st.session_state.rule_selection.get(rule_id, False) for rule_id in rule_ids)
            st.session_state.group_selection[group_id] = any_child


def render_sidebar(config):
    preset_ids = get_all_preset_ids(config)

    st.sidebar.header("清洗规则")

    preset_matching = sync_preset_before_widgets(config)

    st.sidebar.selectbox(
        "预设方案",
        options=preset_ids,
        format_func=lambda pid: get_preset_label(config, pid),
        key=PRESET_STATE_KEY,
        on_change=on_preset_change,
    )

    st.sidebar.markdown("---")

    btn_col1, btn_col2 = st.sidebar.columns(2)
    if btn_col1.button("全选", use_container_width=True):
        for rule_id in st.session_state.rule_selection:
            st.session_state.rule_selection[rule_id] = True
        for group_id in get_rule_groups(config):
            st.session_state.group_selection[group_id] = True
        st.session_state.result = None
        st.rerun()

    if btn_col2.button("全不选", use_container_width=True):
        for rule_id in st.session_state.rule_selection:
            st.session_state.rule_selection[rule_id] = False
        for group_id in get_rule_groups(config):
            st.session_state.group_selection[group_id] = False
        st.session_state.result = None
        st.rerun()

    st.sidebar.markdown("**选择规则**")
    render_grouped_rule_checkboxes(config)

    st.session_state.group_selection = sync_group_selection(
        config, st.session_state.rule_selection, st.session_state.group_selection
    )
    request_preset_resync_if_needed(config, preset_matching)


def render_cleaning(config):
    uploaded = st.file_uploader("上传 Excel 文件", type=["xlsx", "xls"])

    if uploaded is not None:
        st.subheader("数据预览")
        preview_bytes = uploaded.getvalue()
        try:
            preview_df = pd.read_excel(BytesIO(preview_bytes))
            st.dataframe(preview_df.head(20), use_container_width=True)
            st.caption(f"共 {len(preview_df)} 行，仅展示前 20 行")
        except Exception as exc:
            st.error(f"无法预览文件: {exc}")
            return

    enabled_rule_ids = get_enabled_rule_ids(config)
    st.caption(f"当前已生效 {len(enabled_rule_ids)} 条规则")

    if st.button("开始清洗", type="primary", disabled=uploaded is None):
        if not enabled_rule_ids:
            st.error("请至少选择一条生效的清洗规则")
            return

        with st.spinner("正在清洗..."):
            try:
                uploaded.seek(0)
                result = process_upload(
                    uploaded.getvalue(),
                    uploaded.name,
                    config,
                    enabled_rule_ids,
                    CONFIG_LABEL,
                )
                st.session_state.result = result
            except Exception as exc:
                st.error(str(exc))
                return

    result = st.session_state.result
    if result is None:
        return

    st.success(f"清洗完成，耗时 {result['elapsed']:.2f} 秒")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("原始行数", result["total_rows"])
    col2.metric("保留行数", result["kept_rows"])
    col3.metric("删除行数", result["deleted_rows"])
    col4.metric("保留比例", f"{result['kept_rows'] / result['total_rows']:.1%}")

    if not result["summary_df"].empty:
        st.subheader("删除原因统计")
        chart_df = result["summary_df"][result["summary_df"]["删除原因"] != "总计"]
        st.bar_chart(chart_df.set_index("删除原因"))
        st.dataframe(result["summary_df"], use_container_width=True)

    st.subheader("下载结果")
    d1, d2, d3 = st.columns(3)
    d1.download_button(
        "下载 Format.xlsx",
        data=result["format_bytes"],
        file_name=result["format_filename"],
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    d2.download_button(
        "下载 Deleted.xlsx",
        data=result["deleted_bytes"],
        file_name=result["deleted_filename"],
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    d3.download_button(
        "下载 RunConfig.json",
        data=result["run_config_bytes"],
        file_name=result["run_config_filename"],
        mime="application/json",
        use_container_width=True,
    )

    with st.expander("查看保留数据预览"):
        st.dataframe(result["df_kept"].head(50), use_container_width=True)


def render_main(config):
    st.title("Excel 联系人清洗")
    st.caption("上传含 email / affiliation / country 列的 Excel，按分层规则筛选并下载结果。")

    st.info(
        "隐私提示：上传文件会在 Streamlit 云服务器上临时处理，请勿上传高度敏感数据。"
        " 敏感名单请克隆仓库后在本地运行 `streamlit run app.py`。"
    )

    tab_clean, tab_rules = st.tabs(["数据清洗", "规则详情"])

    with tab_rules:
        render_rule_details(config)

    with tab_clean:
        render_cleaning(config)


def main():
    st.set_page_config(
        page_title="Excel 联系人清洗",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session_state()

    config = load_config_data()
    ensure_rule_selection(config)

    render_sidebar(config)
    render_main(config)


if __name__ == "__main__":
    main()
