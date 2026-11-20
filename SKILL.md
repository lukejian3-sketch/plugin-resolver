---
name: plugin-resolver
description: 做项目前自动发现、下载、安装并调用本地插件，能复用就不重复造轮子
whenToUse: 在动手写代码/实现某个功能之前，先判断任务所需能力是否已有现成插件
role: general
enabled: true
---

# 插件解析器（Plugin Resolver）

在做任何项目/功能之前，先跑一遍能力发现：判断任务所需能力是否已有现成插件，
有则自动下载安装并调用，没有才自己实现（DIY）。这就是「第一阶段自动装、第二阶段直调」。

## 工程位置
`__PLUGIN_RESOLVER_ROOT__`
- 一键安装：运行仓库里的 `install.ps1`（Windows）或 `install.sh`（macOS/Linux），会自动把上面占位符替换成本机实际路径。
- 手动安装：直接把上面路径改成你 clone 的插件工程根目录。
首次使用前先执行 `python tools/build_registry.py` 生成市场清单与签名密钥（密钥不会入库）。

## 什么时候用它
用户提出「做某个功能 / 处理某类数据 / 实现某件事」时，在写代码前，先让本解析器查一遍能力目录。

## 用法（在工程目录下执行）

1. 日常运行（首次 `install`，之后自动 `cache-hit` 直调）：
   ```powershell
   $env:PYTHONUTF8='1'
   python main.py "<任务描述>" --registry
   ```

2. 想看匹配到了哪些能力、在哪一层命中（L1 关键词 / L2 语义 / L3 相似度）：
   ```powershell
   python main.py "<任务描述>" --registry --explain
   ```

3. 需要隔离执行（防止恶意/死循环插件拖挂主进程）：
   ```powershell
   python main.py "<任务描述>" --registry --isolated --timeout 5
   ```

## 新增或更新插件后
```powershell
python tools/build_registry.py          # 打包进 registry（含签名）
```

## 插件怎么加
在 `demo/source/<插件名>/` 下放两个文件：
- `manifest.json`：id / name / version / triggers（触发词）/ capabilities（能力）/
  dependencies（依赖，可选）/ rating / downloads / entry / download
- `plugin.py`：暴露 `run(request, resolve=None)`

然后执行 `python tools/build_registry.py` 就完成了发布。

## 能力目录来源
- `catalog/catalog.json` —— 内置清单
- `registry/registry.json` —— 打包发布清单（含 sha256 + 签名）
- `catalog/semantics.json` —— 语义同义词词典（让「没直接说关键词」的说法也能命中）

## 结果字段
`status`: ok / missing / error
`action`: install / upgrade / cache-hit
`dependencies`: 递归安装的依赖能力清单