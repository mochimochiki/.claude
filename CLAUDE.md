## 日本語の書き方
- 日本語を出力するときは、チャットの返答・文書・コードコメント・コミットメッセージ・PR 本文のどれでも、必ず `readable` スキルに従って書く。セッションで初めて日本語を書く前にスキルを読み込む
- 既存の文章の書き直しを頼まれたときは `yomiyasu` スキルを使う

## ルール
- エージェントの作業用ディレクトリは `.agent/tasks`、`.agent/adr.md`、`.agent/roadmaps` とする。既存の慣例があればそれに従う
- `/docs` 以下は確定事項を書く場所で、状態の置き場ではない。例外として、`TODO: {短文で内容}` という短いフラグだけは書いてよい

## CI 失敗の切り分け
CIが `failure`/`cancelled` ならジョブが実際に走ったか確認する。
`runner_name` が空、実行時間が数秒、ステップが0、または注釈に "Actions budget"/"was not started"/"spending limit" とある場合は、ジョブが起動していないだけで、失敗ではない。
この場合は、編集も再実行の連打もせず、予算またはインフラによるブロックとして報告する。
確認には MCP の `get_workflow_job` か、`gh api repos/<o>/<r>/actions/runs/<run_id>/jobs` と `.../check-runs/<job_id>/annotations` を使う。