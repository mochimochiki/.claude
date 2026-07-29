# .claude

Claude Code の個人設定（スキル・ルール）をまとめたリポジトリ。

## セットアップ

`scripts/setup.sh` を実行すると、次の 3 つが行われる。

1. このリポジトリの内容を `~/.claude` に配置する
2. apm（AI エージェント向けの設定管理ツール）が入っていなければ入れる
3. 外部で公開されている impeccable スキルを apm 経由で `~/.claude/skills/impeccable` に入れる

```bash
curl -fsSL https://raw.githubusercontent.com/mochimochiki/.claude/260726/scripts/setup.sh | bash
```

impeccable は apm が管理するため、このリポジトリには含めない。
入れ直したいときは `apm install -g --target claude pbakaus/impeccable` を実行する。
