# Plugin Resolver｜为 DSH 提供可复用的插件能力

在 DSH 执行任务前，先查找已有插件：找到后**自动安装并调用**，后续任务**复用本地安装**；没有匹配能力时，再由智能体继续按常规方式处理。

> 注意：resolver 本身**不生成**缺失插件，只负责「发现 → 安装 → 调用」已有插件。

## 它解决了什么（一个 DSH 对话场景）

```
用户在 DSH 里提出任务
      ↓
DSH 智能体调用 plugin-resolver 查找「需要的能力」
      ↓
命中 ── 首次：自动安装并调用                （action = install）
     └─ 之后再提同类任务：复用本地安装直调   （action = cache-hit）
未命中 ── 回到智能体，继续按常规方式处理
```

> **用户通过 DSH 提任务**；命令行 `python main.py` 是**调试入口**，用来查看解析过程，不是主要使用方式。

## 三个角色，各司其职

| 角色 | 由谁承担 | 做什么 |
|---|---|---|
| 注册 | `install.ps1` / `install.sh` | 把 `SKILL.md` 复制进 `~/.dsh/skills/`（**只写用户目录，不改 DSH 本体**）|
| 调度 | `SKILL.md`（DSH skill）| 指导 DSH 智能体：做任务前先调用 resolver 查已有能力 |
| 执行 | `src/resolver.py` + installer + runtime | 匹配、下载/安装、执行插件，维护本地索引 |

一句话：**安装脚本注册 skill → skill 指导智能体调用 resolver → resolver 负责匹配、安装、执行插件**。

## 快速开始（三步）

### 第 1 步：获取项目并注册 skill

```powershell
git clone https://github.com/lukejian3-sketch/plugin-resolver.git
cd plugin-resolver

powershell -ExecutionPolicy Bypass -File install.ps1    # Windows
# 或 bash install.sh                                     # macOS / Linux
```

成功后会看到：`已安装 skill 到: ~/.dsh/skills/plugin-resolver.md`（并把本机工程路径写入其中）。

### 第 2 步：生成示例插件市场

```powershell
python tools/build_registry.py
```

成功后会看到：`已发布 5 个插件 -> registry\registry.json`（含签名）。

### 第 3 步：在 DSH 里输入一条示例任务

在 DSH 对话中直接说：

```
帮我压缩一段 json 并生成 csv 报告
```

- **首次**：智能体自动安装 `json-minify` + `csv-report` 并调用（`action = install`）
- **再说一次同样的话**：直接复用本地安装（`action = cache-hit`）

想用命令行观察解析过程（可选）：

```bash
python main.py "压缩json" --registry --explain
```

## 当前范围（能做什么 / 限制）

**示例能力**：`minify-json`（两个实现，用于演示多候选择优）、`csv-report`、`report-bundle`（组合 + 依赖）、`slow-job`（沙箱/超时演示）。

**插件格式**：`manifest.json` + `plugin.py`，入口暴露 `run(request, resolve=None)`。

**匹配方式**：L1 关键词触发 → L2 语义词典 → L3 相似度兜底。

**下载类型**：`local`（目录复制）、`zip`（本地包）、`url`（HTTP 下载）；`git` 为预留分支。

**限制**：
- 命令行演示使用**内置示例数据**，不是直接处理任意用户文件；
- 签名用 HMAC 对称密钥（演示用），生产宜换 Ed25519/RSA 非对称；
- 沙箱是「子进程 + 超时」隔离，非 OS 级隔离。

## 路线图

- [ ] `git` 下载分支落地
- [ ] 签名升级为非对称（Ed25519/RSA）
- [ ] 更丰富的市场元数据（兼容性约束、多候选选择策略扩展）
- [ ] 匹配器升级 LLM / embedding

## 目录结构

```
plugin-resolver/
├── main.py                    # CLI 调试入口
├── SKILL.md                   # DSH skill 定义（install 脚本会复制它）
├── install.ps1 / install.sh   # 一键注册 skill 到 ~/.dsh/skills/
├── catalog/
│   ├── catalog.json           # 内置能力目录
│   └── semantics.json         # 语义同义词词典（L2 匹配）
├── src/
│   ├── models.py              # Manifest / DownloadSpec / InstalledPlugin / Index
│   ├── catalog.py             # 加载能力目录 + 多候选择优
│   ├── matcher.py             # 分层语义匹配（L1/L2/L3）
│   ├── index_store.py         # 本地已装索引 + 自愈重建
│   ├── installer.py           # 下载 / 校验 / 验签 / 解压
│   ├── net.py                 # HTTP 下载
│   ├── runtime.py             # 进程内运行时（resolve 依赖注入）
│   ├── isolated_runtime.py    # 进程沙箱（超时终止）
│   ├── plugin_host.py         # 沙箱子进程宿主
│   └── resolver.py            # 核心编排
├── demo/source/               # 示例插件源
│   ├── json_minify/           # minify-json（评分 4.8）
│   ├── json_trimmer/          # minify-json（评分 3.0，多候选择优演示）
│   ├── csv_report/            # csv-report
│   ├── report_bundle/         # report-bundle（依赖 minify-json + csv-report）
│   └── slow_plugin/           # slow-job（沙箱/超时演示）
├── tools/
│   ├── build_registry.py      # 打包 + 签名发布
│   └── simulate_tamper.py     # 模拟攻击者（演示签名验签）
├── registry/                  # 生成的市场清单与发行包（不入库，用 build_registry 生成）
├── plugins/                   # 已安装插件落盘目录（运行时生成，不入库）
└── index.json                 # 本地已装索引（运行时生成，不入库）
```

## 技术细节（速查）

### 命令速查

```bash
python main.py "压缩json" --registry          # 运行一个任务（首装 install，再跑 cache-hit）
python main.py "压缩json" --registry --explain # 查看匹配明细（能力/层级/命中词）
python main.py "压缩json" --registry --isolated --timeout 5  # 沙箱隔离执行
python main.py "压缩json" --registry --rebuild  # 索引自愈重建
python main.py "压缩json" --registry --no-cache # 强制冷启动
```

### 核心决策流

```
请求文本
  -> matcher.match(text)                  # 命中触发词 -> [cap1, cap2, ...]
  -> 对每个 capability:
       index.has_capability(cap)?         # 查本地索引
         ├─ 命中 & 版本一致 -> cache-hit -> 直调
         ├─ 命中 & 版本过旧   -> upgrade  -> 重装
         └─ 未命中           -> install  -> 下载/校验/验签/安装/写索引 -> 调用
  -> 无插件提供该能力 -> 返回 missing（交由智能体继续处理）
```

### 关键设计点

1. **索引粒度是「能力」不是「插件」**：一个插件可提供多个能力，一个能力可被多个插件满足。
2. **多候选择优**：同一能力多个候选时按「评分/下载量」择优（`prefer="rating"`，可扩展）。
3. **校验 + 验签**：`download.sha256` 验完整性，HMAC-SHA256 验来源；伪造包拒绝安装。
4. **依赖递归 + 循环检测**：`manifest.dependencies` 递归安装，stack 去重防死循环。
5. **自愈**：`index_store.rebuild()` 按 `plugins/` 目录重建索引。
6. **匹配器可替换**：升级 LLM/embedding 时只改 `matcher.py`，其他层不变。

### 依赖解析

`manifest.dependencies` 列出依赖的其他能力；安装前先递归确保依赖就绪，运行层用 `resolve(dep_capability, payload)` 注入依赖产出（插件可写 `run(request, resolve)` 双参数签名）。

```bash
python main.py "帮我打包生成综合汇总" --registry   # report-bundle 自动装上两个依赖
```

### 语义匹配（L1 / L2 / L3）

- L1 触发词（manifest.triggers）
- L2 语义词典（catalog/semantics.json）
- L3 字符 bigram 相似度兜底

```bash
python main.py "压缩json" --explain                 # L1 命中
python main.py "把内容精简一下" --explain           # L2 命中（没提「压缩」）
python main.py "把数据变成逗号分隔的文本" --explain # L2 命中（没提「csv」）
```

### 安全：发行包签名 + 进程沙箱

1. **签名验签（防伪造）**：发布时 HMAC-SHA256 签名，安装时验 sha256 + 验签。
   ```bash
   python tools/simulate_tamper.py json-minify   # 模拟篡改 + 伪造 sha256
   python main.py "压缩json" --registry          # 验签失败 -> status=error 拒绝安装
   python tools/build_registry.py                # 恢复
   ```
2. **进程沙箱（防死循环）**：`--isolated` 独立子进程执行，超时自动终止。
   ```bash
   python main.py "跑一个很慢的任务" --registry --isolated --timeout 2
   ```

### 约定

每个插件的入口文件（`manifest.entry`，默认 `plugin.py`）暴露：

```python
def run(request: dict) -> Any:
    ...

# 或需要调用依赖能力时：
def run(request: dict, resolve=None) -> Any:
    ...
```