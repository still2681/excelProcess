import os
from io import BytesIO

import pandas as pd
import streamlit as st

from rule_engine import get_rules_by_id, load_config, process_upload

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_OPTIONS = {
    "完整规则集": os.path.join(BASE_DIR, "config", "package.json"),
    "精简规则集": os.path.join(BASE_DIR, "package-simple.json"),
}
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


def describe_rule_logic(rule):
    match_mode = rule.get("match_mode")
    if match_mode == "builtin":
        return BUILTIN_LABELS.get(rule.get("builtin", ""), "内置规则")

    field = rule.get("field", "")
    mode_label = MATCH_MODE_LABELS.get(match_mode, match_mode)
    scope = SCOPE_LABELS.get(rule.get("scope", "global"), rule.get("scope", "global"))
    return f"作用字段: {field} | 匹配方式: {mode_label} | 范围: {scope}"


def render_rule_details(config):
    st.subheader("规则详情")
    st.caption("查看每条规则的具体匹配逻辑和完整关键词列表。")

    group_labels = config.get("group_labels", {})
    rules = sorted(config.get("rules", []), key=lambda r: r.get("order", 0))

    filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 2])
    with filter_col1:
        group_filter = st.selectbox(
            "规则分组",
            ["全部"] + [group_labels.get(g, g) for g in GROUP_ORDER],
        )
    with filter_col2:
        scope_filter = st.selectbox("显示范围", ["全部规则", "仅已勾选规则"])
    with filter_col3:
        keyword = st.text_input("搜索关键词", placeholder="在国家/邮箱/机构关键词中搜索…")

    if scope_filter == "仅已勾选规则":
        rules = [r for r in rules if st.session_state.rule_selection.get(r["id"], False)]

    if group_filter != "全部":
        selected_group = next(
            (g for g in GROUP_ORDER if group_labels.get(g, g) == group_filter),
            None,
        )
        if selected_group:
            rules = [r for r in rules if r.get("group") == selected_group]

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
        enabled = st.session_state.rule_selection.get(rule["id"], False)
        status = "已启用" if enabled else "未启用"
        header = f"{'✅' if enabled else '⬜'} L{level} · {rule['name']}（{group}）"

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
    if "last_config_key" not in st.session_state:
        st.session_state.last_config_key = None
    if "result" not in st.session_state:
        st.session_state.result = None


def load_active_config(config_key):
    config_path = CONFIG_OPTIONS[config_key]
    config = load_config(config_path)
    return config_path, config


def ensure_rule_selection(config):
    config_key = st.session_state.active_config_key
    if st.session_state.last_config_key != config_key:
        st.session_state.rule_selection = {
            rule["id"]: rule.get("default_enabled", False)
            for rule in config.get("rules", [])
        }
        st.session_state.last_config_key = config_key
        st.session_state.result = None

    for rule in config.get("rules", []):
        st.session_state.rule_selection.setdefault(rule["id"], rule.get("default_enabled", False))


def get_preset_options(config):
    presets = config.get("presets", {})
    return [(pid, info["label"]) for pid, info in presets.items() if pid != "custom"]


def apply_preset(config, preset_id):
    preset_rules = set(config["presets"][preset_id].get("rules", []))
    for rule in config.get("rules", []):
        st.session_state.rule_selection[rule["id"]] = rule["id"] in preset_rules


def get_enabled_rule_ids(config):
    rules_by_id = get_rules_by_id(config)
    selected = [rid for rid, enabled in st.session_state.rule_selection.items() if enabled]
    return sorted(selected, key=lambda rid: rules_by_id.get(rid, {}).get("order", 999))


def render_sidebar(config):
    st.sidebar.header("清洗规则")

    preset_options = get_preset_options(config)
    preset_labels = [label for _, label in preset_options]
    preset_id_by_label = {label: pid for pid, label in preset_options}

    selected_label = st.sidebar.selectbox("预设方案", preset_labels)
    if st.sidebar.button("应用预设", use_container_width=True):
        apply_preset(config, preset_id_by_label[selected_label])
        st.session_state.result = None
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.caption("完整关键词与匹配逻辑请切换到主界面 **规则详情** 标签页。")
    st.sidebar.caption("也可手动勾选下方规则")

    if st.sidebar.button("全选", use_container_width=True):
        for rule_id in st.session_state.rule_selection:
            st.session_state.rule_selection[rule_id] = True
        st.session_state.result = None
        st.rerun()

    if st.sidebar.button("全不选", use_container_width=True):
        for rule_id in st.session_state.rule_selection:
            st.session_state.rule_selection[rule_id] = False
        st.session_state.result = None
        st.rerun()

    group_labels = config.get("group_labels", {})
    rules_by_group = {group: [] for group in GROUP_ORDER}
    for rule in sorted(config.get("rules", []), key=lambda r: r.get("order", 0)):
        rules_by_group.setdefault(rule.get("group", "other"), []).append(rule)

    with st.sidebar.expander("选择规则", expanded=True):
        for group in GROUP_ORDER + [g for g in rules_by_group if g not in GROUP_ORDER]:
            group_rules = rules_by_group.get(group, [])
            if not group_rules:
                continue

            st.markdown(f"**{group_labels.get(group, group)}**")
            for rule in group_rules:
                level = rule.get("level", 0)
                label = f"L{level} {rule['name']}"
                checked = st.checkbox(
                    label,
                    value=st.session_state.rule_selection.get(rule["id"], False),
                )
                st.session_state.rule_selection[rule["id"]] = checked


def render_cleaning(config_key, config):
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
    st.caption(f"当前已选 {len(enabled_rule_ids)} 条规则")

    if st.button("开始清洗", type="primary", disabled=uploaded is None):
        if not enabled_rule_ids:
            st.error("请至少选择一条清洗规则")
            return

        with st.spinner("正在清洗..."):
            try:
                uploaded.seek(0)
                result = process_upload(
                    uploaded.getvalue(),
                    uploaded.name,
                    config,
                    enabled_rule_ids,
                    config_key,
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


def render_main(config_key, config_path, config):
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
        render_cleaning(config_key, config)


def main():
    st.set_page_config(
        page_title="Excel 联系人清洗",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session_state()

    config_key = st.sidebar.selectbox("规则配置", list(CONFIG_OPTIONS.keys()))
    st.session_state.active_config_key = config_key
    config_path, config = load_active_config(config_key)
    ensure_rule_selection(config)

    render_sidebar(config)
    render_main(config_key, config_path, config)


if __name__ == "__main__":
    main()
