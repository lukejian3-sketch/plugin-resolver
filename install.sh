#!/usr/bin/env bash
# install.sh —— 把 plugin-resolver 一键注册成 DSH 全局 skill
# 用法（在仓库根目录）： bash install.sh   （或先 chmod +x install.sh 再 ./install.sh）
set -euo pipefail

DSH_HOME="${DSH_HOME:-$HOME/.dsh}"
SKILLS_DIR="$DSH_HOME/skills"
SKILL_NAME="plugin-resolver.md"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SCRIPT_DIR/SKILL.md"
DST="$SKILLS_DIR/$SKILL_NAME"

if [ ! -f "$SRC" ]; then
  echo "找不到 $SRC —— 请在仓库根目录运行本脚本" >&2
  exit 1
fi

mkdir -p "$SKILLS_DIR"

# 把工程根目录占位符替换为实际绝对路径
sed "s|__PLUGIN_RESOLVER_ROOT__|$SCRIPT_DIR|g" "$SRC" > "$DST"

echo ""
echo "已安装 skill 到: $DST"
echo "插件工程目录已写入: $SCRIPT_DIR"
echo ""
echo "下一步："
echo "  1) 若 DSH 未热加载，重启 dsh web"
echo "  2) 在工程目录首次运行: python3 tools/build_registry.py"
echo "  3) 之后直接对智能体说任务即可，它会自动走 plugin-resolver 能力发现"
echo ""