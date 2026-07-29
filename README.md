# .claude

Claude Code の個人設定（スキル・ルール）をまとめたリポジトリ。

## 外部スキルについて

他の人が公開しているスキルは、このリポジトリには入れずに `apm.yml` へ名前だけ書いておく。
apm（AI エージェント用の設定をまとめて管理するツール）がそれを読んで
`~/.claude/skills/` に配置する。

現在の対象:

- [impeccable](https://github.com/pbakaus/impeccable) — デザインまわりのスキル

## セットアップ

環境構築時に実行するスクリプトとして、以下を登録する。

```bash
#!/bin/bash
set -euo pipefail

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# 1. このリポジトリを ~/.claude に置く
git clone --depth 1 -b 260726 https://github.com/mochimochiki/.claude.git "$TMP"
mkdir -p "$HOME/.claude"
cp -a "$TMP/." "$HOME/.claude/"

# 2. apm コマンドが無ければ入れる（~/.local/bin に置くので sudo は不要）
export PATH="$HOME/.local/bin:$PATH"
if ! command -v apm >/dev/null 2>&1; then
  curl -fsSL https://aka.ms/apm-unix -o "$TMP/apm-install.sh"
  APM_INSTALL_DIR="$HOME/.local/bin" sh "$TMP/apm-install.sh"
fi

# 3. apm.yml に書いた外部スキルを入れる
mkdir -p "$HOME/.apm"
cp "$HOME/.claude/apm.yml" "$HOME/.apm/apm.yml"
apm install -g
```

手順 3 は `apm.yml` を apm の設定場所（`~/.apm/`）へ写してから読ませている。
apm はこの場所のファイルしか見ないため、リポジトリ側を正としてそのつど上書きする。
`apm install -g <名前>` で別のスキルを個別に入れていた場合、この上書きで消える点に注意。

スキルを増やしたいときは `apm.yml` の `dependencies.apm` に一行足す。
