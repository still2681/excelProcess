# Excel 联系人清洗

面向学术邮件名单的分层清洗工具。支持按预设或自定义规则组合，过滤邮箱、机构、国家等不符合条件的联系人。

## 在线使用

部署到 [Streamlit Community Cloud](https://share.streamlit.io) 后，打开应用链接即可使用。

> **隐私提示**：在线版会在 Streamlit 云服务器上临时处理上传文件。请勿上传高度敏感数据；敏感名单请本地运行。

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

桌面版（tkinter）仍可使用：

```bash
python main.py
python process_v2.py
```

## 功能

- **分层规则**：邮箱 / 机构 / 国家 / 姓名规则可按 L1–L3 粒度单独开关
- **双层勾选**：规则组总开关 + 组内子规则（如机构-商业：后缀 / 关键词 / 公司名）
- **删除 / 保留**：删除规则先执行，保留规则（国家白名单、中国精英校）最后执行
- **预设方案**：完整清洗、基础清洗、轻度商业、中国专项、MMailer 印度等
- **输出文件**：
  - `*-Format.xlsx` — 保留数据
  - `*-Deleted.xlsx` — 删除明细 + 原因统计
  - `*-RunConfig.json` — 本次启用的规则

## 项目结构

```
app.py              # Streamlit 在线入口
rule_engine.py      # 核心清洗引擎
config/package.json # 规则配置
main.py             # 本地 tkinter 入口
process_v2.py       # 本地 tkinter 入口
```

## Streamlit Cloud 部署

1. 将本仓库 push 到 GitHub（public）
2. 登录 [share.streamlit.io](https://share.streamlit.io) → **New app**
3. 选择仓库、分支 `main`、主文件 `app.py`
4. 点击 **Deploy**

## 规则配置

规则定义在 `config/package.json` 中，每条规则包含 `id`、`level`、`action`、`match_mode`、`patterns` 等字段。修改 JSON 即可调整关键词，无需改 Python 代码。
