#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""note.com のダッシュボード統計(全体ビュー・スキ・コメント)を取得して記録する。

https://note.com/sitesettings/stats が内部で使っている API
(https://note.com/api/v1/stats/pv)から全期間の記事別統計を取得し、
合計値を CSV に1日1行で追記する。同じ日に複数回実行した場合は上書きされる。

必要な環境変数:
  NOTE_COOKIE ... note.com のログイン Cookie。次のいずれかの形式で指定する:
    1. ブラウザ拡張(Cookie-Editor など)でエクスポートした JSON 配列
       (tools/note_auto_post で使う note_cookies.json と同じもの)
    2. "_note_session_v5=xxxx" のような Cookie ヘッダー文字列
    3. _note_session_v5 の値そのもの

出力:
  data/stats.csv           ... 日次サマリー(date, total_pv, total_likes, ...)
  data/raw/YYYY-MM-DD.json ... その日に取得した記事別の生データ(将来の再集計用)
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# テスト時にモックサーバーへ向けられるよう、接続先だけ差し替え可能にしておく
API_BASE = os.environ.get("NOTE_STATS_API_BASE", "https://note.com")
API_PATH = "/api/v1/stats/pv?filter=all&page={page}&sort=pv"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
MAX_PAGES = 100
JST = timezone(timedelta(hours=9))

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = REPO_ROOT / "data" / "stats.csv"
RAW_DIR = REPO_ROOT / "data" / "raw"
CSV_FIELDS = [
    "date",
    "total_pv",
    "total_likes",
    "total_comments",
    "article_count",
    "last_calculate_at",
]

AUTH_ERROR_MESSAGE = """
note.com にログインできませんでした。Cookie が未設定か、期限切れの可能性があります。

対処方法:
  1. ふだんのブラウザで note.com にログインする
  2. Cookie をエクスポートする(どちらかの方法で)
     - 拡張機能「Cookie-Editor」で note.com を開いて Export → JSON
     - F12 → アプリケーション → Cookie → https://note.com → _note_session_v5 の値をコピー
  3. GitHub リポジトリの Settings → Secrets and variables → Actions で
     NOTE_COOKIE を New repository secret(2回目以降は鉛筆マークで更新)として保存する
""".strip()


def build_cookie_header(raw: str) -> str:
    """NOTE_COOKIE の3形式(JSON配列 / ヘッダー文字列 / 値のみ)を Cookie ヘッダーに変換する。"""
    raw = raw.strip()
    if raw.startswith("["):
        try:
            cookies = json.loads(raw)
        except json.JSONDecodeError as e:
            raise SystemExit(f"NOTE_COOKIE の JSON を解析できません: {e}")
        pairs = [
            f"{c['name']}={c['value']}"
            for c in cookies
            if isinstance(c, dict)
            and c.get("name")
            and "note.com" in str(c.get("domain", "note.com"))
        ]
        if not pairs:
            raise SystemExit("NOTE_COOKIE の JSON 内に note.com の Cookie が見つかりません。")
        return "; ".join(pairs)
    if "=" in raw:
        return raw
    return f"_note_session_v5={raw}"


def fetch_page(cookie_header: str, page: int) -> dict:
    url = API_BASE + API_PATH.format(page=page)
    req = urllib.request.Request(
        url,
        headers={
            "Cookie": cookie_header,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                body = res.read().decode("utf-8", errors="replace")
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                # ログインページ(HTML)にリダイレクトされた場合など
                raise SystemExit(AUTH_ERROR_MESSAGE)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise SystemExit(AUTH_ERROR_MESSAGE)
            last_error = e
        except urllib.error.URLError as e:
            last_error = e
        time.sleep(3 * (attempt + 1))
    raise SystemExit(f"note.com への接続に失敗しました: {last_error}")


def to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def read_count_of(stat: dict) -> int:
    # API 仕様変更に備えて、ビュー数として使われそうなキーを順に試す
    for key in ("read_count", "pv", "page_view", "view_count"):
        if key in stat:
            return to_int(stat.get(key))
    return 0


def fetch_all_stats(cookie_header: str) -> dict:
    """全ページを取得して、記事別リストと合計値をまとめて返す。"""
    all_stats: list[dict] = []
    last_calculate_at = None
    for page in range(1, MAX_PAGES + 1):
        payload = fetch_page(cookie_header, page)
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        stats = data.get("note_stats") or data.get("stats") or []
        all_stats.extend(s for s in stats if isinstance(s, dict))
        last_calculate_at = data.get("last_calculate_at") or last_calculate_at
        # last_page キーが無い場合や記事が無い場合はそこで打ち切る(無限ループ防止)
        if data.get("last_page") is not False or not stats:
            break
        time.sleep(0.5)
    return {
        "fetched_at": datetime.now(JST).isoformat(timespec="seconds"),
        "last_calculate_at": last_calculate_at,
        "note_stats": all_stats,
    }


def summarize(snapshot: dict) -> dict:
    stats = snapshot["note_stats"]
    return {
        "date": datetime.now(JST).date().isoformat(),
        "total_pv": sum(read_count_of(s) for s in stats),
        "total_likes": sum(to_int(s.get("like_count")) for s in stats),
        "total_comments": sum(to_int(s.get("comment_count")) for s in stats),
        "article_count": len(stats),
        "last_calculate_at": snapshot.get("last_calculate_at") or "",
    }


def upsert_csv_row(row: dict) -> None:
    """同じ日付の行があれば置き換え、なければ追記して日付順に保存する。"""
    rows: list[dict] = []
    if CSV_PATH.exists():
        with CSV_PATH.open(newline="", encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r.get("date")]
    rows = [r for r in rows if r["date"] != row["date"]]
    rows.append({k: str(row.get(k, "")) for k in CSV_FIELDS})
    rows.sort(key=lambda r: r["date"])
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    raw_cookie = os.environ.get("NOTE_COOKIE", "")
    if not raw_cookie.strip():
        raise SystemExit(
            "環境変数 NOTE_COOKIE が設定されていません。\n\n" + AUTH_ERROR_MESSAGE
        )
    cookie_header = build_cookie_header(raw_cookie)

    snapshot = fetch_all_stats(cookie_header)
    if not snapshot["note_stats"]:
        raise SystemExit(
            "統計データが1件も取得できませんでした。"
            "Cookie の期限切れか、API の仕様変更の可能性があります。\n\n" + AUTH_ERROR_MESSAGE
        )
    row = summarize(snapshot)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"{row['date']}.json"
    raw_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    upsert_csv_row(row)

    print(f"記録しました: {row['date']}")
    print(f"  全体ビュー : {row['total_pv']:,}")
    print(f"  スキ       : {row['total_likes']:,}")
    print(f"  コメント   : {row['total_comments']:,}")
    print(f"  記事数     : {row['article_count']}")
    print(f"  集計時刻   : {row['last_calculate_at']}")


if __name__ == "__main__":
    main()
