# ea-cwh — Encre Agent 插件市场中央索引

`ea-cwh` 是插件市场目录数据的**唯一权威载体**：一个纯数据 Python 包，内部只有一
份 `catalog.json`，描述中央仓库中每一个已发布插件的展示信息与安装坐标。

- 市场后端**不联网渲染**：定时 `pip install -U ea-cwh` 升级本包，然后本地读取。
- 升级失败自动沿用上一次的好数据（后端另有 `data/market_catalog.json` 缓存兜底）。
- 文件由 registry 仓库 CI 在每次合并后自动重新生成并发布，**禁止手改**。

## 条目 schema（schema_version = 1）

```json
{
  "schema_version": 1,
  "generated_at": "2026-10-01T00:00:00+00:00",
  "registry": "https://pypi.org",
  "plugins": [
    {
      "name": "pgvector",
      "pypi_package": "ea-plugin-pgvector",
      "version": "1.2.0",
      "description": "Vector search tools for Encre Agent",
      "author": "Dunimd Team",
      "icon": "database",
      "license": "Apache-2.0",
      "homepage": "https://github.com/dunimd/ea-plugin-pgvector",
      "repository": "https://github.com/dunimd/ea-plugin-pgvector",
      "docs": "",
      "email": "",
      "tags": ["database", "vector"],
      "permissions": ["tools:register"],
      "provides": { "tools": ["vector_search"], "skills": [] },
      "min_encre_version": "0.5.0",
      "artifacts": {
        "ea_plugin_pgvector-1.2.0-py3-none-any.whl": {
          "sha256": "<64 hex>",
          "size": 123456
        }
      },
      "published_at": "2026-09-30T12:00:00+00:00",
      "yanked": false
    }
  ]
}
```

硬性约束（`validate_catalog` 强制）：

1. `pypi_package` 必须以保留前缀 **`ea-plugin-`** 开头（名称保留策略见下文）。
2. `version` 必须钉死具体版本，禁止范围表达式。
3. 每个 `artifacts` 文件必须带 **sha256**，安装端在导入任何代码前校验。
4. `name` 与 `pypi_package` 全局唯一。

## 读取 API

```python
import ea_cwh

ea_cwh.catalog()              # 校验后的完整文档（违规抛 ValueError）
ea_cwh.plugins()              # 条目列表（默认剔除 yanked）
ea_cwh.get("pgvector")        # 按插件名查条目
ea_cwh.by_pypi_package("ea-plugin-pgvector")
ea_cwh.index_version()        # 本包版本 = 索引构建戳
```

## 仓库结构与 CI

本仓库即 Encre Agent 插件市场的中央 registry（`mf2023/ea-cwh`）：

```
ea-cwh/
├── .github/workflows/       # validate-catalog.yml + publish-index.yml
├── catalog.d/<name>.json    # 每个插件一个条目文件（由 encre-plugin publish 写入）
├── ea_cwh/                  # 索引包源码（catalog.json 由 CI 生成，禁止手改）
├── tools/regen_catalog.py   # CI 用的合并/校验/PyPI 交叉核对脚本（零依赖）
└── pyproject.toml           # ea-cwh 包清单（版本号由 CI bump）
```

两个工作流：

1. **validate-catalog.yml（PR 闸门）**——作者本地执行
   `encre-plugin publish --registry-dir <registry 仓库检出>` 会先上传
   PyPI，再向 registry 仓库提交只含 `catalog.d/<name>.json` 的 PR。CI
   重新合并全部条目并校验 schema，再逐个核对 PyPI 上是否存在该
   `pypi_package==version` 且 wheel 的 sha256 与索引承诺完全一致——
   校验不过就不许合并，"合并"即意味着"可安装且字节一致"。
2. **publish-index.yml（合并即发布）**——PR 合入 main 后触发：重新生成
   `ea_cwh/catalog.json` → 以 `0.<日期>.<run号>` 打新索引版本 → 构建
   data wheel → **trusted publishing（OIDC）发布 ea-cwh 到 PyPI** → 把
   重新生成的 catalog.json 提交回 main。各 Encre Agent 后端每日升级
   `ea-cwh` 即可拿到新索引。

### 一次性配置

- **PyPI trusted publishing**：在 ea-cwh 项目页 Publishing → Trusted
  Publisher，添加仓库 = `mf2023/ea-cwh`、workflow =
  `publish-index.yml`、environment = `pypi`。索引发布全程零长期 token。
- **插件作者的 PyPI 权限**：每个 `ea-plugin-*` 项目同样建议配置 trusted
  publishing（指向插件自己的仓库 CI）；作者本机一次性发布则用
  `__token__` API token（twine 默认读取）。

### 名称保留

PyPI 没有官方前缀保留机制，防线由索引侧构成：`validate_catalog` 强制
`ea-plugin-` 前缀，PR 闸门核对钉死版本与 sha256，抢注/篡改的包永远过不了
合并。建议另做一次加固：把当前目录里已知的每个 `ea-plugin-*` 名称先在
PyPI 上传一个占位版本，防止外部抢注后再被误加进索引。

### `encre-plugin publish` 的 GitHub 权限

CLI 开 registry PR 用作者本机的 `git push` + `gh pr create`：协作者直推
需要 registry 仓库的 fine-grained PAT（Contents: Read/Write + Pull
requests: Read/Write）；外部贡献者走 fork 流程，用 `gh auth login` 自身
权限即可。

