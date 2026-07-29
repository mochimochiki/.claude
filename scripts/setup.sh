#!/bin/bash
set -eu

# 環境をセットアップするスクリプト。
#   1. この設定リポジトリを ~/.claude に展開する
#   2. apm（AI エージェント向けの設定管理ツール）を用意する
#   3. 外部で公開されている impeccable スキルを apm 経由で入れる

# 1. 設定リポジトリを取得して ~/.claude に置く
TMP=$(mktemp -d)
git clone --depth 1 https://github.com/mochimochiki/.claude.git "$TMP" -b 260726
mkdir -p "$HOME/.claude"
cp -a "$TMP/." "$HOME/.claude/"
rm -rf "$TMP"

# 2. apm コマンドが無ければ入れる（~/.local/bin に置くので sudo は不要）
export PATH="$HOME/.local/bin:$PATH"
if ! command -v apm >/dev/null 2>&1; then
  curl -fsSL https://aka.ms/apm-unix | APM_INSTALL_DIR="$HOME/.local/bin" sh
fi

# 3. impeccable スキルを入れる
#    -g          : 特定のプロジェクトではなく利用者全体の設定として入れる
#    --target claude : Claude Code 用として ~/.claude/skills/ に配置する
#    バージョンを固定したい場合は末尾に #skill-v4.0.3 のようにタグを付ける
apm install -g --target claude pbakaus/impeccable
