# note-article

note記事の制作と投稿を支援するリポジトリです。

## /note_auto — note記事自動生成プロンプト

`.claude/commands/note_auto.md` に、note記事自動生成プロンプト v1.0 を
Claude Code のスラッシュコマンドとして収録しています。

Claude Code でこのリポジトリを開き、`/note_auto` と入力すると発動します。

- 通常モード：ヒアリング → 構成設計（承認必須）→ 執筆 → 自己検証 → 付帯情報生成
- 引数付き起動：`/note_auto テーマ：◯◯ 文字数：◯◯`（引数で埋まる質問はスキップ）
- 推敲モード：既存の下書き本文を貼ってから `/note_auto` と入力
- 途中で「リセット」と入力すると最初からやり直せます

生成される付帯情報：概要文、見出し画像プロンプト（日本語・英語）、
ハッシュタグ、推奨マガジン、エンゲージメント施策、投稿推奨タイミング。

## tools/note_auto_post — note下書き自動入力ツール

生成した記事（frontmatter付きMarkdown）を note.com の下書きへ
自動入力するPlaywrightスクリプトです。詳細は `tools/note_auto_post/` を参照。

```bash
cd tools/note_auto_post
node post.js --file ./articles/sample.md [--cookies ./note_cookies.json]
```

公開ボタンは自動で押しません。内容を確認のうえ手動で投稿してください。
