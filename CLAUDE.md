## ルール
- 読み手が前提知識を持たない前提で、専門用語を減らし、具体的で平易な日本語で書く
- 特に慣例がなければ `.agent/tasks` `.agent/adr.md`, `.agent/roadmaps` をエージェントの作業用ディレクトリとする。既存の慣例があればそれに従う
- `/docs` 以下は確定事項を書く場所で、状態の置き場ではない。唯一 `TODO: {短文で内容}` という短いフラグは可。

## CI 失敗の切り分け
CIが `failure`/`cancelled` ならジョブが実際に走ったか確認する。
`runner_name` 空・実行数秒・ステップ0、注釈 "Actions budget"/"was not started"/"spending limit" はジョブ未起動で失敗ではない
編集も再実行連打もせず、予算/インフラブロックとして報告。
確認: MCP `get_workflow_job`、または `gh api repos/<o>/<r>/actions/runs/<run_id>/jobs` と `.../check-runs/<job_id>/annotations`