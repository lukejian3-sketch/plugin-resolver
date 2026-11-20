# Plugin Resolver —— 带本地索引的插件解析器（最小可运行工程）

把你说的两个阶段收敛成**一条 resolver 路径**：

- **第一阶段（冷启动）**：索引未命中 → `下载/复制 → sha256 校验 → 安装 → 写索引 → 调用`
- **第二阶段（热启动）**：索引命中 → `直调`

两阶段共用同一个 `resolve_and_invoke`，差别只是 `index.json` 的缓存命中率。

## 安装到 DSH（一键）

把本仓库注册成 DSH 的全局 skill，注册后对智能体直接说任务即可自动走能力发现，不用再手动敲 `python main.py`。

```powershell
# Windows（在仓库根目录）
powershell -ExecutionPolicy Bypass -File install.ps1

# macOS / Linux（在仓库根目录）
bash install.sh        # 或： chmod +x install.sh && ./install.sh
```

脚本会把 `SKILL.md` 复制到 `~/.dsh/skills/plugin-resolver.md`，并把插件工程的本机实际路径自动写入其中。安装后若技能目录未热加载，重启 dsh web 即可。

## 目录结构

```
plugin-resolver/
├── main.py                 # CLI 演示入口
├── catalog/
│   └── catalog.json        # ① 能力目录：有哪些插件、提供哪些能力、怎么下载
├── src/
│   ├── models.py           # Manifest / DownloadSpec / InstalledPlugin / Index
│   ├── catalog.py          # 加载能力目录
│   ├── matcher.py          # ② 意图匹配器（分层语义：L1关键词/L2同义词/L3相似度）
│   ├── index_store.py      # ③ 本地已装索引 + 自愈重建
│   ├── installer.py        # ④ 安装器：copy / 校验 / 落盘
│   ├── runtime.py          # ⑤ 调用运行时：加载插件入口 run(request)
│   └── resolver.py         # 核心编排
├── demo/source/            # 示例插件源（被“安装”到 plugins/ 的那份）
│   ├── json_minify/
│   └── csv_report/
├── plugins/                # 已安装插件落盘目录（installer 写入）
└── index.json              # 本地已装索引（resolver 自动维护）
```

## 运行

```bash
# 1) 冷启动：能力未装，走 install 路径
python main.py "压缩这段 json 并生成 csv 报告"

# 2) 再次执行同一条：索引命中，走 cache-hit 直调（第二阶段）
python main.py "压缩这段 json 并生成 csv 报告"

# 3) 查看意图匹配明细
python main.py "压缩json" --explain

# 4) 强制体验冷启动（清空索引）
python main.py "压缩json" --no-cache

# 5) 索引自愈：删除 index.json 后按 plugins/ 重建
python main.py "压缩json" --rebuild
```

观察第 1、2 步输出里的 `"action"` 字段：第一次是 `install`，第二次是 `cache-hit`。

## 核心决策流

```
请求文本
  -> matcher.match(text)                # 命中触发词 -> [cap1, cap2, ...]
  -> 对每个 capability:
       index.has_capability(cap)?       # 查本地索引
         ├─ 命中 & 版本一致 -> cache-hit -> 直调
         ├─ 命中 & 版本过旧   -> upgrade  -> 重装
         └─ 未命中           -> install  -> 下载/校验/安装/写索引 -> 调用
  -> 无插件提供该能力 -> 返回 missing(走 DIY)
```

## 关键设计点

1. **索引粒度是「能力」不是「插件」**：一个插件可提供多个能力，一个能力可被多个插件满足（可做 fallback，当前 `find_by_capability` 用首个命中，可加权重）。
2. **校验与版本锁定**：`download.sha256` 对入口文件校验，未填则跳过（demo 留空；生产建议填）。
3. **可扩展下载类型**：MVP 实现 `local`；`_fetch` 中已留 `url` / `git` 分支，接上真实仓库补一个分支即可。
4. **自愈**：`index_store.rebuild(plugins_dir)` 按插件目录里的 manifest 重建索引，解决索引与磁盘不一致。
5. **匹配器可替换**：`SemanticMatcher` 分层匹配（L1 触发词 / L2 语义词典 / L3 相似度兜底），升级到 LLM/embedding 时只替换 `matcher.py`，其他层不受影响。

## 插件市场（registry）：自动发现 + 打包下载

把能力目录从「手写静态清单」升级为「从插件市场自动发现」：

```bash
# 1) 发布：把 demo/source 各插件打成 zip + 生成 registry.json（含 zip sha256 指纹）
python tools/build_registry.py

# 2) 消费（第一阶段：自动发现 + 下载安装 + 调用）
python main.py "压缩这段 json 并生成 csv 报告" --registry

# 3) 再次运行走 cache-hit（第二阶段）
python main.py "压缩这段 json 并生成 csv 报告" --registry
```

`--registry` 会把 catalog 来源切成 `registry/registry.json`，installer 走 `zip` 分支：**下载 zip → 校验 sha256 → 解压 → 安装**。

## 真实网络下载（url 分支）+ 版本升级

1. 起本地插件市场（HTTP server）：
   ```bash
   python -m http.server 8765 --bind 127.0.0.1
   ```

2. 发布远程清单（download.type=url，source 为完整 URL）：
   ```bash
   python tools/build_registry.py --base-url http://127.0.0.1:8765 --out registry.remote.json
   ```

3. 消费（真实从 URL 下载 zip）：
   ```bash
   python main.py "压缩这段 json 并生成 csv 报告" --registry-url http://127.0.0.1:8765/registry/registry.remote.json
   ```

安装器 `url` 分支：`src/net.py::download` 下载 zip → 校验 sha256 → 解压。

版本升级：resolver 用 `is_newer(catalog_ver, installed_ver)` 做 semver 比较，
catalog 版本更新时自动走 `upgrade` 重装；本地版本不低于 catalog 时不降级（继续用本地）。

## 依赖解析（递归安装 + 循环检测）

manifest 的 `dependencies` 字段列出该插件依赖的其他能力。resolver 在安装某插件前，
先递归确保依赖能力已就绪（`resolver._ensure`），并带循环依赖检测（stack 去重，
命中返回 cycle 而非死循环）。

示例：`report-bundle` 依赖 `minify-json` + `csv-report`。

```bash
python main.py "帮我打包生成综合汇总" --registry
```

第一次会看到 report-bundle 的 `dependencies` 里自动装上两个依赖；再次运行走 cache-hit。

运行层注入：插件可写 `run(request, resolve)`，用 `resolve(dep_capability, payload)` 调用依赖能力并取回产出（见 demo/source/report_bundle/plugin.py）。Runtime 用 inspect 自适应单/双参数签名，旧插件 `run(request)` 无需改动。

## 语义匹配（分层：L1/L2/L3）

匹配器不再只靠关键词子串，而是分层：

- L1 规则触发词（manifest.triggers）权重最高、可解释；
- L2 语义词典（catalog/semantics.json 同义词）处理变体说法；
- L3 字符 bigram 相似度兜底（前两层无命中时的模糊关联）。

```bash
python main.py "压缩json" --explain                 # L1 命中
python main.py "把内容精简一下" --explain           # L2 命中（没提「压缩」也命中 minify-json）
python main.py "把数据变成逗号分隔的文本" --explain # L2 命中（没提「csv」也命中 csv-report）
```

## 市场元数据 + 多候选择优

同一能力可被多个插件提供（如 minify-json 由 json-minify 4.8 分 与 json-trimmer 3.0 分
两个实现）。`Catalog.candidates_for(cap)` 返回所有候选，`find_by_capability` 按
评分/下载量择优（`prefer="rating"`，可扩展策略）。

```bash
python main.py "压缩json" --registry   # 自动选评分更高的 json-minify
```

## 安全：发行包签名 + 进程沙箱

自动下载并执行插件的系统，两条安全底线：

1. 签名验签（防伪造）：发布时用 HMAC-SHA256 对发行包签名（tools/signing.key），
   安装时先验 sha256（完整性）再验签名（来源认证），伪造包会被拒绝。
   ```bash
   python tools/simulate_tamper.py json-minify   # 模拟攻击者篡改 + 伪造 sha256
   python main.py "压缩json" --registry          # 验签失败 -> status=error 拒绝安装
   python tools/build_registry.py                # 恢复
   ```
   注：HMAC 是对称签名，生产应换成 Ed25519/RSA 非对称（发布者持私钥、消费者持公钥）。

2. 进程沙箱（防恶意/死循环插件）：`--isolated` 用独立子进程执行插件，超时自动终止。
   ```bash
   python main.py "跑一个很慢的任务" --registry --isolated --timeout 2
   ```
   恶意/死循环插件超时后被隔离终止，不影响 resolver 主进程。

## 如何扩展一个真实插件仓库

1. `catalog.json` 增加一条 manifest，`download.type` 改为 `url`（或 `git`），`source` 指向压缩包地址。
2. `installer._fetch` 里给对应 type 加下载 + 解压逻辑。
3. 生产里给 `download.sha256` 填入口文件校验值，生成方式：

   ```bash
   python -c "from src.installer import sha256_file; from pathlib import Path; print(sha256_file(Path('demo/source/json_minify/plugin.py')))"
   ```

## 约定

每个插件的入口文件（`manifest.entry`，默认 `plugin.py`）暴露：

```python
def run(request: dict) -> Any:
    ...
```