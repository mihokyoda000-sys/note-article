#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""data/stats.csv から note のアクセス数グラフ(docs/stats.png)を生成する。

上段: 全体ビューの累計の推移(折れ線)
下段: 前回取得からの増加ビュー数(棒)
データがまだ無い場合は案内メッセージだけの画像を出力する。
"""
from __future__ import annotations

import csv
from datetime import datetime, date as date_type, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))

import matplotlib

matplotlib.use("Agg")

# 日本語フォント(CI では matplotlib-fontja を入れる)。無ければ英語表記に切り替える。
try:
    import matplotlib_fontja  # noqa: F401

    HAS_JP_FONT = True
except ImportError:
    try:
        import japanize_matplotlib  # noqa: F401

        HAS_JP_FONT = True
    except ImportError:
        HAS_JP_FONT = False

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = REPO_ROOT / "data" / "stats.csv"
OUT_PATH = REPO_ROOT / "docs" / "stats.png"

# カラーパレット(ライトサーフェス用に検証済みの既定値)
SURFACE = "#fcfcfb"
SERIES = "#2a78d6"  # 青(系列1)
INK = "#0b0b0b"  # 主要テキスト
INK_2 = "#52514e"  # 補助テキスト
MUTED = "#898781"  # 軸ラベル
GRID = "#e1e0d9"  # グリッド(ヘアライン)
BASELINE = "#c3c2b7"  # 軸線

T = {
    True: {
        "title": "note 全体ビュー(アクセス数)の推移",
        "cumulative": "累計ビュー",
        "daily": "増加ビュー数(前回の記録との差)",
        "updated": "最終更新",
        "total": "累計",
        "views_unit": "ビュー",
        "no_data": "まだデータがありません。\n毎日20時の自動実行(または手動実行)後にグラフが表示されます。",
        "need_two": "増加数は2日分のデータが揃うと表示されます",
    },
    False: {
        "title": "note.com total views",
        "cumulative": "Cumulative views",
        "daily": "New views since previous record",
        "updated": "Updated",
        "total": "Total",
        "views_unit": "views",
        "no_data": "No data yet.\nThe graph will appear after the first daily run.",
        "need_two": "Daily change appears once two days of data exist",
    },
}[HAS_JP_FONT]


def load_rows() -> list[dict]:
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        rows = []
        for r in csv.DictReader(f):
            try:
                rows.append(
                    {
                        "date": date_type.fromisoformat(r["date"]),
                        "total_pv": int(r["total_pv"]),
                    }
                )
            except (KeyError, ValueError):
                continue
    rows.sort(key=lambda r: r["date"])
    return rows


def style_axis(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.spines["bottom"].set_linewidth(1)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))


def new_figure(height: float = 6.6):
    fig = plt.figure(figsize=(10, height), facecolor=SURFACE)
    return fig


def save(fig) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PATH, dpi=160, facecolor=SURFACE, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)
    print(f"グラフを出力しました: {OUT_PATH}")


def render_placeholder() -> None:
    fig = new_figure(4.2)
    fig.text(0.5, 0.62, T["title"], ha="center", fontsize=15, color=INK)
    fig.text(0.5, 0.42, T["no_data"], ha="center", va="center", fontsize=11, color=INK_2, linespacing=1.8)
    save(fig)


def bar_width_days(ax, dates: list[date_type]) -> float:
    """棒の太さ(日数単位)。24px 以下・棒どうしに 2px 以上の隙間、を満たすように計算する。"""
    slot = 1.0
    if len(dates) >= 2:
        slot = min((b - a).days or 1 for a, b in zip(dates, dates[1:]))
    ax.figure.canvas.draw()
    x0, x1 = ax.get_xlim()
    span_days = max(x1 - x0, 1e-9)
    px_per_day = ax.get_window_extent().width / span_days
    max_by_px = 24.0 / px_per_day  # 太さ 24px 以下
    max_by_gap = slot - (2.0 / px_per_day)  # 隣と 2px 以上の隙間
    width = min(0.72 * slot, max_by_px, max_by_gap)
    return max(width, 0.05 * slot)


def render_chart(rows: list[dict]) -> None:
    dates = [r["date"] for r in rows]
    totals = [r["total_pv"] for r in rows]
    deltas = [b - a for a, b in zip(totals, totals[1:])]

    fig = new_figure()
    gs = fig.add_gridspec(2, 1, height_ratios=[2.0, 1.1], hspace=0.42)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])

    # ---- 上段: 累計ビューの折れ線 ----
    style_axis(ax1)
    ax1.plot(
        dates,
        totals,
        color=SERIES,
        linewidth=2,
        solid_capstyle="round",
        solid_joinstyle="round",
        zorder=3,
    )
    # 終端マーカー(サーフェス色の 2px リング付き)と、終端のみ直接ラベル
    ax1.plot(
        dates[-1],
        totals[-1],
        marker="o",
        markersize=9,
        color=SERIES,
        markeredgecolor=SURFACE,
        markeredgewidth=2,
        zorder=4,
    )
    ax1.annotate(
        f"{totals[-1]:,}",
        (dates[-1], totals[-1]),
        textcoords="offset points",
        xytext=(8, 4),
        fontsize=11.5,
        color=INK,
    )
    ax1.set_title(T["cumulative"], loc="left", fontsize=11, color=INK_2, pad=10)
    ax1.set_ylim(bottom=0)
    ax1.margins(x=0.04)
    if len(dates) == 1:
        # 1点だけのときは前後3日に絞る(既定だと数年分の軸になってしまう)
        ax1.set_xlim(dates[0] - timedelta(days=3), dates[0] + timedelta(days=3))

    # ---- 下段: 増加ビュー数の棒 ----
    style_axis(ax2)
    ax2.set_title(T["daily"], loc="left", fontsize=11, color=INK_2, pad=10)
    if deltas:
        bar_dates = dates[1:]
        ax2.set_xlim(ax1.get_xlim())  # 上下段で期間を揃える
        width = bar_width_days(ax2, bar_dates)
        ax2.bar(bar_dates, deltas, width=width, color=SERIES, zorder=3)
        ax2.axhline(0, color=BASELINE, linewidth=1, zorder=2)
        # 最新の棒だけ値を直接ラベル
        latest = deltas[-1]
        ax2.annotate(
            f"{latest:+,}",
            (bar_dates[-1], max(latest, 0)),
            textcoords="offset points",
            xytext=(0, 5),
            ha="center",
            fontsize=10,
            color=INK_2,
        )
        if min(deltas) >= 0:
            ax2.set_ylim(bottom=0)
    else:
        ax2.set_xlim(ax1.get_xlim())
        ax2.text(
            0.5,
            0.5,
            T["need_two"],
            transform=ax2.transAxes,
            ha="center",
            va="center",
            fontsize=10,
            color=MUTED,
        )
        ax2.set_yticks([])

    # ---- タイトルと更新情報 ----
    fig.suptitle(T["title"], x=0.045, y=0.985, ha="left", fontsize=15.5, color=INK)
    updated = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    fig.text(
        0.045,
        0.925,
        f"{T['updated']}: {updated} JST   {T['total']}: {totals[-1]:,} {T['views_unit']}",
        fontsize=10,
        color=INK_2,
    )
    fig.subplots_adjust(top=0.86, bottom=0.08, left=0.075, right=0.97)
    save(fig)


def main() -> None:
    rows = load_rows()
    if not rows:
        render_placeholder()
    else:
        render_chart(rows)


if __name__ == "__main__":
    main()
