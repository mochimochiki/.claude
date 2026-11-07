# .claude

Claude Codeの個人設定（スキル・ルール）をまとめたリポジトリ。

## セットアップ

環境構築時に実行するスクリプトとして、次の内容を登録する。

```bash
#!/bin/bash
set -euo pipefail

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# 1. このリポジトリを ~/.claude に置く
git clone --depth 1 -b main https://github.com/mochimochiki/.claude.git "$TMP"
mkdir -p "$HOME/.claude"
cp -a "$TMP/." "$HOME/.claude/"

# 2. apm コマンドが無ければ入れる（~/.local/bin に置くので sudo は不要）
export PATH="$HOME/.local/bin:$PATH"
if ! command -v apm >/dev/null 2>&1; then
  python3 -m pip install --user --quiet apm-cli
fi

# 3. apm.yml に書いた外部スキルを入れる
mkdir -p "$HOME/.apm"
cp "$HOME/.claude/apm.yml" "$HOME/.apm/apm.yml"
apm install -g
```

### 手順2でpipを使う理由

apmの公式の入れ方は `curl https://aka.ms/apm-unix | sh` だが、`aka.ms` への接続が
許可されていない環境があり、そこでは403で失敗する。
apmはPyPIにも `apm-cli` という名前で置かれているため、そちらから入れている。

### 手順3が回りくどい理由

`apm install -g` は実行した場所ではなく `~/.apm/apm.yml` だけを読む。
そのため、リポジトリの `apm.yml` をそこへ写してから実行している。
この写しは毎回リポジトリ側の内容で上書きする。そのため、`apm install -g <名前>` で
個別に入れたスキルは、この上書きで消える。

### スキルを増やしたいとき

`apm.yml` の `dependencies.apm` に1件足す。GitHubのAPIを使わずに済むよう、
`git:` にクローンURL、`ref:` にタグを書く形にそろえている。
