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

### 手順 2 が pip 経由な理由

apm の公式の入れ方は `curl https://aka.ms/apm-unix | sh` だが、`aka.ms` への接続が
許可されていない環境があり、そこでは 403 で失敗する。
apm は PyPI にも `apm-cli` という名前で置かれているため、そちらから入れている。

### 手順 3 が回りくどい理由

`apm install -g` は実行した場所ではなく `~/.apm/apm.yml` だけを読む。
そのため、リポジトリの `apm.yml` をそこへ写してから実行している。
リポジトリ側を正として毎回上書きするので、`apm install -g <名前>` で
別のスキルを個別に入れていた場合はこの上書きで消える点に注意。

### スキルを増やしたいとき

`apm.yml` の `dependencies.apm` に一件足す。GitHub の API を使わずに済むよう、
`git:` にクローン URL、`ref:` にタグを書く形で揃えている。
