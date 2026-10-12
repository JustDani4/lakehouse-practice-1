"""Графики отчёта из results/trino_*.json -> img/chart_*.png

Все метрики берутся медианой по прогонам, чтобы один шумный прогон не решал.
1. тепловые карты формат x кодек по трём метрикам;
2. индекс относительно несжатого Parquet (= 100);
3. наклонные линии cold -> warm (эффект кэша);
4. пузырьковая диаграмма: запись x чтение, площадь = объём;
5. разброс между прогонами: каждый прогон точкой, медиана чертой.
"""
import csv
import glob
import statistics
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

PQ, ORC = "#4a3aa7", "#1baf7a"                      # violet / aqua, validated pair
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e4e0", "#fcfcfb"
SEQ = LinearSegmentedColormap.from_list(            # blue ramp, steps 100..650
    "seq", ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#104281"])

FORMATS, CODECS = ["PARQUET", "ORC"], ["NONE", "SNAPPY", "GZIP", "ZSTD"]
COLOR = {"PARQUET": PQ, "ORC": ORC}

plt.rcParams.update({
    "font.size": 10, "text.color": INK, "axes.labelcolor": MUTED,
    "axes.edgecolor": GRID, "xtick.color": MUTED, "ytick.color": MUTED,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
})

import json
entries = [json.loads(p.read_text()) for p in __import__('pathlib').Path('results').glob('trino_*.json')]
assert len(entries)==8, 'Run all eight combinations first'
NUM = ('gb', 'data_bytes', 'meta_bytes', 'write_sec', 'cold_sec', 'warm_sec')
runs = [{(r['format'],r['codec']): {k: (r['reads'][i][k] if k in ('cold_sec','warm_sec') else r[k]) for k in NUM} for r in entries} for i in range(3)]
val = {key: {k: statistics.median(run[key][k] for run in runs) for k in NUM} for key in runs[0]}
base = val[('PARQUET','NONE')]


def clean(ax, keep=("bottom",)):
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(s in keep)
    ax.tick_params(length=0)


def spread(ys, gap):
    """Раздвинуть y-координаты подписей, чтобы между соседними было не меньше gap."""
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    out = list(ys)
    for a, b in zip(order, order[1:]):
        out[b] = max(out[b], out[a] + gap)
    return out


def save(fig, name):
    fig.tight_layout()
    fig.savefig(f"img/{name}", dpi=160)
    plt.close(fig)


# --- 1. тепловые карты -----------------------------------------------------
metrics = [("gb", "Объём, ГиБ", "{:.3f}"), ("write_sec", "Запись, с", "{:.1f}"),
           ("cold_sec", "Q18 после рестарта, с", "{:.2f}")]
fig, axes = plt.subplots(1, 3, figsize=(11, 2.9))
for ax, (key, title, fmt) in zip(axes, metrics):
    grid = [[val[(f, c)][key] for c in CODECS] for f in FORMATS]
    lo, hi = min(map(min, grid)), max(map(max, grid))
    ax.imshow(grid, cmap=SEQ, vmin=lo, vmax=hi, aspect="auto")
    for i, row in enumerate(grid):
        for j, v in enumerate(row):
            dark = (v - lo) / (hi - lo or 1) > 0.55
            ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=10,
                    color="white" if dark else INK, fontweight="bold" if v == lo else None)
    ax.set_xticks(range(4), [c.lower() for c in CODECS])
    ax.set_yticks(range(2), ["Parquet", "ORC"])
    ax.set_title(title, loc="left", fontsize=11, pad=8)
    clean(ax, keep=())
fig.suptitle("Формат × кодек: светлее — лучше, жирным — лучший вариант",
             x=0.01, ha="left", fontsize=12)
save(fig, "chart_heatmap.png")

# --- 2. индекс к несжатому Parquet ----------------------------------------
panels = [("gb", "Объём"), ("write_sec", "Запись"), ("cold_sec", "После рестарта"),
          ("warm_sec", "Повтор")]
order = [(f, c) for f in FORMATS for c in CODECS]
fig, axes = plt.subplots(1, 4, figsize=(11, 3.8), sharey=True)
for ax, (key, title) in zip(axes, panels):
    idx = [val[k][key] / base[key] * 100 for k in order]
    bars = ax.barh(range(len(order)), idx, height=0.62,
                   color=[COLOR[f] for f, _ in order], edgecolor=SURFACE, linewidth=2)
    for t in ax.bar_label(bars, fmt="%.0f", padding=3, fontsize=8, color=MUTED):
        t.set_bbox(dict(facecolor=SURFACE, edgecolor="none", pad=0.5))
    ax.axvline(100, color=MUTED, lw=1, ls=(0, (3, 3)))
    ax.set_title(title, loc="left", fontsize=11)
    ax.set_xlim(0, max(idx) * 1.22)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    clean(ax)
axes[0].set_yticks(range(len(order)), [f"{f.lower()} · {c.lower()}" for f, c in order])
axes[0].invert_yaxis()
handles = [plt.Rectangle((0, 0), 1, 1, color=COLOR[f]) for f in FORMATS]
fig.legend(handles, ["Parquet", "ORC"], frameon=False, ncol=2, loc="upper right")
fig.suptitle("Индекс к parquet · none = 100 (меньше — лучше)", x=0.01, ha="left", fontsize=12)
save(fig, "chart_index.png")

# --- 3. after restart versus immediate repeat ------------------------------
fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
for ax, f in zip(axes, FORMATS):
    for i, c in enumerate(CODECS):
        cold, warm = val[(f,c)]['cold_sec'], val[(f,c)]['warm_sec']
        ax.plot([warm,cold],[i,i],color=COLOR[f],lw=3,alpha=.45)
        ax.scatter(cold,i,s=80,facecolor=SURFACE,edgecolor=COLOR[f],linewidth=2,zorder=3)
        ax.scatter(warm,i,s=80,color=COLOR[f],edgecolor=SURFACE,linewidth=1.5,zorder=4)
        ax.text(warm-.08,i-.18,f'{warm:.2f}',ha='right',va='center',fontsize=9,color=MUTED)
        ax.text(cold+.08,i-.18,f'{cold:.2f}  x{cold/warm:.2f}',ha='left',va='center',fontsize=9,color=MUTED)
    ax.set_yticks(range(4),[c.lower() for c in CODECS])
    ax.set_xlim(.9,5.05)
    ax.set_ylim(3.5,-.55)
    ax.set_xlabel('Секунды')
    ax.set_title('Parquet' if f=='PARQUET' else 'ORC',loc='left',fontsize=11)
    ax.grid(axis='x',color=GRID,lw=.8); ax.set_axisbelow(True); clean(ax)
axes[1].scatter([],[],s=70,facecolor=SURFACE,edgecolor=ORC,linewidth=2,label='после рестарта')
axes[1].scatter([],[],s=70,color=ORC,label='повтор')
axes[1].legend(frameon=False,loc='lower right',fontsize=8)
fig.suptitle('TPC-H Q18: первый запрос после рестарта и повтор',x=.01,ha='left',fontsize=12)
save(fig,'chart_cache.png')

# --- 4. пузыри: запись x чтение x объём -----------------------------------
fig, ax = plt.subplots(figsize=(8, 5))
for f in FORMATS:
    for c in CODECS:
        v = val[(f, c)]
        ax.scatter(v["write_sec"], v["cold_sec"], s=v["gb"] * 2600, color=COLOR[f],
                   alpha=0.75, edgecolor=SURFACE, linewidth=2, zorder=3)
        r = (v["gb"] * 2600) ** 0.5 / 2                 # радиус пузыря в пунктах
        ax.annotate(f"{c.lower()} · {v['gb']:.3f} ГиБ", (v["write_sec"], v["cold_sec"]),
                    xytext=(0, r + 4), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8, color=MUTED)
ax.set_xlabel("Запись, с")
ax.set_ylabel("Q18 после рестарта, с")
ax.grid(color=GRID, lw=0.8)
ax.set_axisbelow(True)
ax.margins(0.18)
clean(ax, keep=("bottom", "left"))
for f in FORMATS:
    ax.scatter([], [], s=90, color=COLOR[f], label="Parquet" if f == "PARQUET" else "ORC")
ax.legend(frameon=False, loc="upper left")
ax.set_title("Три метрики сразу: ближе к левому нижнему углу и меньше пузырь — лучше",
             loc="left", fontsize=12, pad=10)
save(fig, "chart_bubble.png")

# --- 5. разброс между прогонами -------------------------------------------
RUN_COLORS = ["#86b6ef", "#2a78d6", "#104281"]          # ordinal blue: run1 -> runN
order = [(f, c) for f in FORMATS for c in CODECS]
fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
for ax, (key, title) in zip(axes, [("cold_sec", "Q18 после рестарта, с"), ("warm_sec", "Q18 повтор, с")]):
    for i, k in enumerate(order):
        xs = [run[k][key] for run in runs]
        ax.plot([min(xs), max(xs)], [i, i], color=GRID, lw=6, solid_capstyle="round", zorder=1)
        for n, x in enumerate(xs):
            ax.scatter(x, i, s=60, color=RUN_COLORS[n % 3], edgecolor=SURFACE, lw=1.5, zorder=3)
        ax.plot([val[k][key]] * 2, [i - 0.3, i + 0.3], color=INK, lw=1.5, zorder=2)
    ax.set_title(title, loc="left", fontsize=11)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    clean(ax)
axes[0].set_yticks(range(len(order)), [f"{f.lower()} · {c.lower()}" for f, c in order])
axes[0].invert_yaxis()
for n in range(len(runs)):
    axes[1].scatter([], [], s=60, color=RUN_COLORS[n % 3], label=f"повтор {n + 1}")
axes[1].plot([], [], color=INK, lw=1.5, label="медиана")
axes[1].legend(frameon=False, loc="lower right", fontsize=9)
fig.suptitle("Разброс времени Q18: три повтора на одной машине",
             x=0.01, ha="left", fontsize=12)
save(fig, "chart_runs.png")

print(f"5 графиков -> img/ (прогонов: {len(runs)})")
