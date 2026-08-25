#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""data/raw/*.json から記事別グラフ(docs/articles.png)を生成する。

上段: 記事別 累計ビューの推移(上位5記事の折れ線。2日分のデータが揃ってから)
中段: 累計ビューの記事ランキング(上位10記事の横棒)
下段: 累計スキの記事ランキング(上位10記事の横棒)
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib.pyplot as plt

from chartstyle import (
    CATEGORICAL,
    HAS_JP_FONT,
    INK,
    INK_2,
    LIKE_COLOR,
    MUTED,
    SERIES,
    SURFACE,
    hbar_height,
    save,
    style_axis,
    style_hbar_axis,
    truncate,
)

JST = timezone(timedelta(hours=9))

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
OUT_PATH = REPO_ROOT / "docs" / "articles.png"

TREND_SERIES = 5  # 推移の折れ線に載せる記事数
RANK_SIZE = 10  # ランキングに載せる記事数

T = {
    True: {
        "title": "note 記事別のアクセス数・スキ",
        "trend": f"記事別 累計ビューの推移(上位{TREND_SERIES}記事)",
        "rank_pv": "累計ビュー ランキング",
        "rank_like": "累計スキ ランキング",
        "updated": "最終更新",
        "articles": "記事",
        "all": "全",
        "top": "上位",
        "no_data": "まだデータがありません。\n6時間ごとの自動実行(または手動実行)後にグラフが表示されます。",
        "need_two": "推移は2回分のデータが揃うと表示されます",
    },
    False: {
        "title": "note.com per-article views & likes",
        "trend": f"Cumulative views per article (top {TREND_SERIES})",
        "rank_pv": "Cumulative views ranking",
        "rank_like": "Cumulative likes ranking",
        "updated": "Updated",
        "articles": "articles",
        "all": "of ",
        "top": "top ",
        "no_data": "No data yet.\nThe graph will appear after the first run.",
        "need_two": "The trend appears once two records exist",
    },
}[HAS_JP_FONT]


def to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def read_count_of(stat: dict) -> int:
    for key in ("read_count", "pv", "page_view", "view_count"):
        if key in stat:
            return to_int(stat.get(key))
    return 0


def parse_stem(stem: str) -> datetime | None:
    """ファイル名(拡張子なし)を日時にする。新形式 "2026-08-25T14" と旧形式 "2026-08-22" の両対応。"""
    try:
        when = datetime.fromisoformat(stem)
    except ValueError:
        return None
    if "T" not in stem:
        when = when.replace(hour=20)  # 旧形式(日付のみ)は毎日20時ごろの取得だった
    return when


def load_snapshots() -> list[tuple[datetime, dict[int, dict]]]:
    """(日時, {記事id: 統計}) のリストを日時順に返す。壊れたファイルは読み飛ばす。"""
    snapshots = []
    for path in sorted(RAW_DIR.glob("*.json")) if RAW_DIR.exists() else []:
        when = parse_stem(path.stem)
        if when is None:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        stats = {
            s["id"]: s
            for s in data.get("note_stats", [])
            if isinstance(s, dict) and s.get("id") is not None
        }
        if stats:
            snapshots.append((when, stats))
    snapshots.sort(key=lambda s: s[0])
    return snapshots


def render_placeholder() -> None:
    fig = plt.figure(figsize=(10, 4.2), facecolor=SURFACE)
    fig.text(0.5, 0.62, T["title"], ha="center", fontsize=15, color=INK)
    fig.text(0.5, 0.42, T["no_data"], ha="center", va="center", fontsize=11, color=INK_2, linespacing=1.8)
    save(fig, OUT_PATH)


def render_trend(ax, snapshots) -> None:
    latest = snapshots[-1][1]
    top_ids = sorted(latest, key=lambda i: read_count_of(latest[i]), reverse=True)[:TREND_SERIES]
    # 色は記事に固定で対応させる(日によって順位が入れ替わっても色が変わらないよう id 順で割り当てる)
    color_of = {aid: CATEGORICAL[i % len(CATEGORICAL)] for i, aid in enumerate(sorted(top_ids))}

    style_axis(ax)
    for aid in top_ids:  # 凡例はビュー数の多い順
        points = [(day, read_count_of(stats[aid])) for day, stats in snapshots if aid in stats]
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        ax.plot(
            xs,
            ys,
            color=color_of[aid],
            linewidth=2,
            solid_capstyle="round",
            solid_joinstyle="round",
            label=truncate(latest[aid].get("name", aid), 16),
            zorder=3,
        )
        ax.plot(
            xs[-1],
            ys[-1],
            marker="o",
            markersize=7,
            color=color_of[aid],
            markeredgecolor=SURFACE,
            markeredgewidth=2,
            zorder=4,
        )
    ax.set_ylim(bottom=0)
    ax.margins(x=0.04)
    ax.legend(
        loc="upper left",
        frameon=False,
        fontsize=8.5,
        labelcolor=INK_2,
        handlelength=1.6,
    )


def render_ranking(ax, latest: dict[int, dict], value_key, color) -> None:
    """横棒ランキング。value_key は統計 dict から値を取り出す関数。"""
    ranked = sorted(latest.values(), key=value_key, reverse=True)[:RANK_SIZE]
    names = [truncate(s.get("name", s.get("id")), 20) for s in ranked]
    values = [value_key(s) for s in ranked]

    style_hbar_axis(ax)
    ax.set_xlim(0, max(max(values), 1) * 1.14)
    height = hbar_height(ax, len(ranked))
    ax.barh(range(len(ranked)), values, height=height, color=color, zorder=3)
    ax.set_yticks(range(len(ranked)), labels=names)
    ax.invert_yaxis()  # 1位を一番上に
    for i, v in enumerate(values):
        ax.annotate(
            f"{v:,}",
            (v, i),
            textcoords="offset points",
            xytext=(5, 0),
            va="center",
            fontsize=9,
            color=INK_2,
        )


def render_chart(snapshots) -> None:
    latest = snapshots[-1][1]
    n_articles = len(latest)
    n_rank = min(RANK_SIZE, n_articles)

    fig = plt.figure(figsize=(10, 12), facecolor=SURFACE)
    gs = fig.add_gridspec(3, 1, height_ratios=[1.5, 1.0, 1.0], hspace=0.5)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])
    ax3 = fig.add_subplot(gs[2])

    # ---- 上段: 記事別ビューの推移 ----
    ax1.set_title(T["trend"], loc="left", fontsize=11, color=INK_2, pad=10)
    if len(snapshots) >= 2:
        render_trend(ax1, snapshots)
    else:
        style_axis(ax1)
        when = snapshots[-1][0]
        ax1.set_xlim(when - timedelta(days=3), when + timedelta(days=3))
        ax1.text(
            0.5, 0.5, T["need_two"], transform=ax1.transAxes,
            ha="center", va="center", fontsize=10, color=MUTED,
        )
        ax1.set_yticks([])

    # ---- 中段・下段: ランキング ----
    rank_suffix = f"{T['top']}{n_rank} / {T['all']}{n_articles}{T['articles']}"
    ax2.set_title(f"{T['rank_pv']}({rank_suffix})", loc="left", fontsize=11, color=INK_2, pad=10)
    render_ranking(ax2, latest, read_count_of, SERIES)
    ax3.set_title(f"{T['rank_like']}({rank_suffix})", loc="left", fontsize=11, color=INK_2, pad=10)
    render_ranking(ax3, latest, lambda s: to_int(s.get("like_count")), LIKE_COLOR)

    # ---- タイトルと更新情報 ----
    fig.suptitle(T["title"], x=0.045, y=0.99, ha="left", fontsize=15.5, color=INK)
    updated = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    fig.text(0.045, 0.955, f"{T['updated']}: {updated} JST", fontsize=10, color=INK_2)
    fig.subplots_adjust(top=0.915, bottom=0.05, left=0.28, right=0.95)
    save(fig, OUT_PATH)


def main() -> None:
    snapshots = load_snapshots()
    if not snapshots:
        render_placeholder()
    else:
        render_chart(snapshots)


if __name__ == "__main__":
    main()
