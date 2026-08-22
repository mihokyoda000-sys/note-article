#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""グラフ共通のスタイル定義(配色・日本語フォント・軸の装飾)。"""
from __future__ import annotations

from pathlib import Path

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

# カラーパレット(ライトサーフェス用に検証済みの既定値)
SURFACE = "#fcfcfb"
SERIES = "#2a78d6"  # 青(系列1)
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]  # 系列1〜5
LIKE_COLOR = "#eb6834"  # スキ用(系列2のオレンジ)
INK = "#0b0b0b"  # 主要テキスト
INK_2 = "#52514e"  # 補助テキスト
MUTED = "#898781"  # 軸ラベル
GRID = "#e1e0d9"  # グリッド(ヘアライン)
BASELINE = "#c3c2b7"  # 軸線


def style_axis(ax) -> None:
    """折れ線・縦棒グラフ用(横軸=日付)の装飾。"""
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


def style_hbar_axis(ax) -> None:
    """横棒ランキング用の装飾。各棒の先端に値を書くので目盛り・グリッドは持たない。"""
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "bottom"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(BASELINE)
    ax.spines["left"].set_linewidth(1)
    ax.grid(False)
    ax.tick_params(colors=INK_2, labelsize=9, length=0)
    ax.xaxis.set_visible(False)


def hbar_height(ax, n: int) -> float:
    """横棒の太さ(スロットに対する割合)。太さ 24px 以下・棒どうしに隙間を保つ。"""
    ax.figure.canvas.draw()
    px_per_slot = ax.get_window_extent().height / max(n, 1)
    return max(min(0.62, 24.0 / px_per_slot), 0.1)


def save(fig, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160, facecolor=SURFACE, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)
    print(f"グラフを出力しました: {out_path}")


def truncate(text: str, limit: int) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"
