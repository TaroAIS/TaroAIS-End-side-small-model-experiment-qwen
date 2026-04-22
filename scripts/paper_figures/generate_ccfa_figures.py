import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib import font_manager
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
import argparse
import json, re, textwrap, math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT/'report'/'formal_paper_canonical_s42_current'
DEFAULT_FIG = DEFAULT_DATA/'paper_figures'
DEFAULT_LOG = ''

parser = argparse.ArgumentParser(description='Generate paper-ready research figures from a result directory.')
parser.add_argument('--data_dir', default=str(DEFAULT_DATA), help='Directory containing metrics_table.csv, task_metrics.csv, and optional error_cases.jsonl/key_task_summary.csv.')
parser.add_argument('--out_dir', default=str(DEFAULT_FIG), help='Output directory for generated figures.')
parser.add_argument('--log_md', default=DEFAULT_LOG, help='Optional markdown log used by some figure annotations.')
args = parser.parse_args()

DATA = Path(args.data_dir).resolve()
FIG = Path(args.out_dir).resolve()
LOG = Path(args.log_md).resolve() if args.log_md else None
FIG.mkdir(parents=True, exist_ok=True)

def pick_font(candidates):
    for path in candidates:
        if Path(path).exists():
            return path
    return None

regular_font = pick_font([
    r'C:\Windows\Fonts\msyh.ttc',
    r'C:\Windows\Fonts\simsun.ttc',
    r'C:\Windows\Fonts\simhei.ttf',
    '/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc',
])
bold_font = pick_font([
    r'C:\Windows\Fonts\msyhbd.ttc',
    r'C:\Windows\Fonts\simhei.ttf',
    '/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc',
    regular_font,
])
FP = font_manager.FontProperties(fname=regular_font)
FPB = font_manager.FontProperties(fname=bold_font)

NAVY = '#23374D'
BLUE = '#4C78A8'
TEAL = '#3D8B8B'
RED = '#C35B5B'
GOLD = '#B8903A'
PURPLE = '#7C6EB0'
GRAY = '#64748B'
LIGHT = '#F4F7FB'
MID = '#D9E2EC'
GRID = '#D8E1EA'
GREEN = '#5A9A6F'
DARK = '#1F2937'
WHITE = '#FFFFFF'

plt.rcParams.update({
    'font.family': font_manager.FontProperties(fname=regular_font).get_name(),
    'font.size': 11,
    'axes.titlesize': 12,
    'axes.labelsize': 11,
    'axes.unicode_minus': False,
    'axes.edgecolor': '#AAB7C4',
    'axes.linewidth': 0.8,
    'grid.color': GRID,
    'grid.linewidth': 0.7,
    'xtick.color': DARK,
    'ytick.color': DARK,
    'text.color': DARK,
    'svg.fonttype': 'none',
})

metrics = pd.read_csv(DATA/'metrics_table.csv')
task = pd.read_csv(DATA/'task_metrics.csv')
key_task_path = DATA/'key_task_summary.csv'
key_task = pd.read_csv(key_task_path) if key_task_path.exists() else pd.DataFrame()

baseline = 'baseline_rag_formal_anchor_4b_canonical'
agent = 'edge_agent_formal_paper_canonical_s42'
label_map = {baseline:'Baseline', agent:'Task-routed'}

overall = metrics.copy()
overall['label'] = overall['method'].map(label_map)

task_map_cn = {'single_doc_qa':'single\_doc\_qa', 'multi_doc_qa':'multi\_doc\_qa', 'code_qa':'code\_qa'}
task_map_short = {'single_doc_qa':'Single-doc', 'multi_doc_qa':'Multi-doc', 'code_qa':'Code'}

task_display_order = ['single_doc_qa','multi_doc_qa','code_qa']

rows=[]
for line in open(DATA/'error_cases.jsonl', encoding='utf-8', errors='ignore'):
    r = json.loads(line)
    s = r['id'][3:] if r['id'].startswith('lb_') else r['id']
    dataset = '_'.join(s.split('_')[:-1])
    r['dataset']=dataset
    rows.append(r)
errors = pd.DataFrame(rows)

dataset_to_task = {
    'narrativeqa':'single_doc_qa','qasper':'single_doc_qa','multifieldqa_en':'single_doc_qa','multifieldqa_zh':'single_doc_qa','dureader':'single_doc_qa',
    'hotpotqa':'multi_doc_qa','2wikimqa':'multi_doc_qa','musique':'multi_doc_qa',
    'lcc':'code_qa','repobench-p':'code_qa'
}
errors['task'] = errors['dataset'].map(dataset_to_task)
errors['method_label'] = errors['method'].map(label_map)
errors['task_label'] = errors['task'].map(task_map_short)

case_studies_path = DATA/'case_studies.md'
case_text = case_studies_path.read_text(encoding='utf-8', errors='ignore') if case_studies_path.exists() else ''
log_text = LOG.read_text(encoding='utf-8', errors='ignore') if LOG and LOG.exists() else ''


def savefig(fig, name):
    fig.savefig(FIG/f'{name}.png', dpi=260, bbox_inches='tight', pad_inches=0.05)
    fig.savefig(FIG/f'{name}.svg', bbox_inches='tight', pad_inches=0.03)
    plt.close(fig)


def fig_ax(size=(10,4)):
    fig, ax = plt.subplots(figsize=size)
    return fig, ax


def set_serif_text(obj, bold=False):
    if isinstance(obj, list):
        for o in obj:
            set_serif_text(o, bold)
        return
    try:
        obj.set_fontproperties(FPB if bold else FP)
    except Exception:
        pass


def clean(ax, grid='y'):
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#AAB7C4')
    ax.spines['bottom'].set_color('#AAB7C4')
    if grid == 'y':
        ax.grid(axis='y', alpha=0.95)
    elif grid == 'x':
        ax.grid(axis='x', alpha=0.95)
    elif grid == 'both':
        ax.grid(alpha=0.95)
    else:
        ax.grid(False)
    set_serif_text(ax.get_xticklabels())
    set_serif_text(ax.get_yticklabels())
    if ax.get_xlabel(): set_serif_text(ax.xaxis.label)
    if ax.get_ylabel(): set_serif_text(ax.yaxis.label)
    if ax.get_title(): set_serif_text(ax.title, True)


def add_box(ax, x, y, w, h, text, fc=WHITE, ec=MID, lw=1.4, fontsize=13, ha='center'):
    patch = FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.02,rounding_size=0.025', facecolor=fc, edgecolor=ec, linewidth=lw)
    ax.add_patch(patch)
    ax.text(x+w/2 if ha=='center' else x+0.03*w, y+h/2, text, ha=ha, va='center', fontsize=fontsize, fontproperties=FP)
    return patch


def arrow(ax, x1,y1,x2,y2, color=GRAY, lw=1.5, style='-|>', ms=14, cs='arc3'):
    arr = FancyArrowPatch((x1,y1),(x2,y2), arrowstyle=style, linewidth=lw, color=color, mutation_scale=ms, connectionstyle=cs)
    ax.add_patch(arr)
    return arr


def fig1_problem_tension():
    fig, ax = plt.subplots(figsize=(12,4.7))
    ax.set_xlim(0,14); ax.set_ylim(0,6); ax.axis('off')
    ax.text(2.3,5.2,'复杂任务', fontproperties=FPB, fontsize=15, color=NAVY, ha='center')
    ax.text(11.7,5.2,'简单任务', fontproperties=FPB, fontsize=15, color=RED, ha='center')
    ax.text(2.3,4.72,'若流程过轻，证据归并不足', fontproperties=FP, fontsize=11.5, color=GRAY, ha='center')
    ax.text(11.7,4.72,'若流程过重，代价与失焦抬升', fontproperties=FP, fontsize=11.5, color=GRAY, ha='center')
    add_box(ax,0.6,2.95,2.0,0.85,'统一轻流程',fc='#EEF4FB',ec=BLUE,fontsize=13.5)
    add_box(ax,5.0,2.62,4.0,1.5,'复杂任务停得太早\n跨证据归并不足，最终答案难收束',fc='#F8FBFF',ec=BLUE,fontsize=14)
    add_box(ax,11.4,2.95,2.0,0.85,'统一重流程',fc='#FDEEEE',ec=RED,fontsize=13.5)
    add_box(ax,5.0,1.0,4.0,1.1,'简单任务被过度处理\n时延、OOM 与答案失焦同步上升',fc='#FFF7F5',ec=RED,fontsize=14)
    arrow(ax,2.6,3.38,5.0,3.38,color=BLUE)
    arrow(ax,9.0,1.55,11.4,3.38,color=RED,cs='arc3,rad=0.18')
    add_box(ax,2.7,0.15,8.6,0.52,'研究目标：在固定预算代理下，为不同任务分配不同深度的问答路径',fc='#F6F8FA',ec='#9AA9B8',fontsize=13.2)
    savefig(fig,'fig1_1_problem_tension')


def fig2_gap_matrix():
    rows = ['单轮 RAG','多步 Agent','轻量化推理','本文框架']
    cols = ['长文档证据处理','预算代理感知','任务异质性','边界显式报告']
    vals = np.array([[1,0,0,0],[1,0,1,0],[0,1,0,0],[1,1,1,1]])
    fig, ax = plt.subplots(figsize=(11.2,4.1))
    ax.axis('off')
    x0,y0,w,h = 0.18,0.16,0.74,0.64
    cw, rh = w/len(cols), h/len(rows)
    for j,c in enumerate(cols):
        t=ax.text(x0+(j+0.5)*cw, y0+h+0.08, c, transform=ax.transAxes, ha='center', va='center', fontsize=12)
        set_serif_text(t, True)
    for i,r in enumerate(rows):
        t=ax.text(x0-0.03, y0+h-(i+0.5)*rh, r, transform=ax.transAxes, ha='right', va='center', fontsize=12)
        set_serif_text(t, i==3)
        for j in range(len(cols)):
            xx = x0+j*cw; yy = y0+h-(i+1)*rh
            face = LIGHT if not vals[i,j] else ('#E1EEF9' if i<3 else '#E3F1E8')
            edge = MID if i<3 else GREEN
            rect = FancyBboxPatch((xx,yy),cw*0.96,rh*0.86,boxstyle='round,pad=0.01,rounding_size=0.012',transform=ax.transAxes,facecolor=face,edgecolor=edge,linewidth=1.0)
            ax.add_patch(rect)
            txt = ax.text(xx+cw*0.48, yy+rh*0.43, '✓' if vals[i,j] else '–', transform=ax.transAxes, ha='center', va='center', fontsize=20, color=(GREEN if i==3 and vals[i,j] else (BLUE if vals[i,j] else '#94A3B8')))
            set_serif_text(txt, vals[i,j])
    note = ax.text(0.5,0.05,'定位不是“再造一条统一更优算法”，而是在任务异质性与预算代理共同约束下重组流程。',transform=ax.transAxes,ha='center',va='center',fontsize=11.5,color=GRAY)
    set_serif_text(note)
    savefig(fig,'fig2_1_research_gap_matrix')


def fig3_eval_scope():
    fig, ax = plt.subplots(figsize=(11.5,4.8))
    ax.set_xlim(0,14); ax.set_ylim(0,7); ax.axis('off')
    add_box(ax,0.6,3.85,3.2,2.2,'固定主评测口径\n2550 样本 / 3 个任务组\n2 条流程：baseline vs task-routed\n质量 + 成本联合报告',fc='#F8FBFF',ec=BLUE,fontsize=14)
    add_box(ax,5.1,3.85,3.8,2.2,'可直接写成事实\noverall F1 上升\ncode\_qa 为当前最强亮点\nsingle\_doc\_qa 明确回撤\np95 与 OOM 成本上升',fc='#F7FAF8',ec=GREEN,fontsize=14)
    add_box(ax,10.2,3.85,3.2,2.2,'不能写成事实\n多 seed 显著性成立\n相对所有强基线都更优\n三任务全面平衡提升',fc='#FFF7F5',ec=RED,fontsize=14)
    add_box(ax,3.1,1.0,7.8,1.5,'证据边界：当前冻结结果来自 single-seed 正式结果，且当前主表只支持“相对 anchor baseline 的局部收益 + 清晰边界”。',fc='#F6F8FA',ec='#9AA9B8',fontsize=13)
    arrow(ax,3.8,4.95,5.1,4.95,color=BLUE)
    arrow(ax,8.9,4.95,10.2,4.95,color=GRAY)
    savefig(fig,'fig3_1_eval_scope')


def fig4_workflow():
    fig, ax = plt.subplots(figsize=(12,4.8))
    ax.set_xlim(0,16); ax.set_ylim(0,8); ax.axis('off')
    add_box(ax,0.5,5.7,2.0,0.9,'问题 + 长上下文',fc=WHITE,ec=MID,fontsize=13.5)
    add_box(ax,3.2,5.7,2.2,0.9,'任务识别 / 路由',fc='#EEF4FB',ec=BLUE,fontsize=13.5)
    add_box(ax,6.2,6.3,2.2,0.8,'single 路径',fc='#F9FAFB',ec='#B8C4CF',fontsize=12.5)
    add_box(ax,6.2,5.1,2.2,0.8,'multi 路径',fc='#F9FAFB',ec='#B8C4CF',fontsize=12.5)
    add_box(ax,6.2,3.9,2.2,0.8,'code 路径',fc='#F9FAFB',ec='#B8C4CF',fontsize=12.5)
    add_box(ax,9.3,5.0,2.5,1.3,'受限检索升级\n事实压缩记忆',fc='#F8FBFF',ec=TEAL,fontsize=13)
    add_box(ax,12.6,5.0,2.3,1.3,'预算守卫\n提前停止',fc='#FFF9F0',ec=GOLD,fontsize=13)
    add_box(ax,12.6,3.2,2.3,1.0,'最终答案收束',fc='#F7FAF8',ec=GREEN,fontsize=13)
    arrow(ax,2.5,6.15,3.2,6.15,color=GRAY)
    arrow(ax,5.4,6.15,6.2,6.7,color=BLUE)
    arrow(ax,5.4,6.15,6.2,5.5,color=BLUE)
    arrow(ax,5.4,6.15,6.2,4.3,color=BLUE)
    arrow(ax,8.4,6.7,9.3,5.95,color=TEAL)
    arrow(ax,8.4,5.5,9.3,5.65,color=TEAL)
    arrow(ax,8.4,4.3,9.3,5.35,color=TEAL)
    arrow(ax,11.8,5.65,12.6,5.65,color=GOLD)
    arrow(ax,13.75,5.0,13.75,4.2,color=GOLD)
    arrow(ax,13.75,4.2,13.75,4.2,color=GOLD)
    arrow(ax,13.75,4.2,13.75,4.2,color=GOLD)
    arrow(ax,13.75,4.2,13.75,4.2,color=GOLD)
    arrow(ax,13.75,4.95,13.75,4.2,color=GOLD)
    arrow(ax,13.75,4.2,13.75,4.2,color=GOLD)
    arrow(ax,13.75,4.15,13.75,4.15,color=GRAY)
    arrow(ax,13.75,4.15,13.75,4.15,color=GRAY)
    arrow(ax,13.75,4.95,13.75,4.2,color=GRAY)
    arrow(ax,13.75,4.2,13.75,4.2,color=GRAY)
    arrow(ax,13.75,4.2,13.75,4.2,color=GRAY)
    arrow(ax,13.75,4.2,13.75,4.2,color=GRAY)
    arrow(ax,13.75,4.95,13.75,4.2,color=GRAY)
    arrow(ax,13.75,4.2,13.75,4.2,color=GRAY)
    arrow(ax,13.75,4.2,13.75,4.2,color=GRAY)
    arrow(ax,13.75,4.95,13.75,4.2,color=GRAY)
    arrow(ax,13.75,4.2,13.75,3.7,color=GRAY)
    arrow(ax,13.75,3.7,13.75,3.7,color=GRAY)
    arrow(ax,13.75,3.7,13.75,3.7,color=GRAY)
    arrow(ax,13.75,3.7,13.75,3.7,color=GRAY)
    arrow(ax,13.75,3.7,13.75,3.7,color=GRAY)
    savefig(fig,'fig4_1_workflow')


def fig4_routing_budget():
    fig, ax = plt.subplots(figsize=(11.5,4.5))
    ax.set_xlim(0,15); ax.set_ylim(0,7); ax.axis('off')
    add_box(ax,0.6,3.0,2.4,1.0,'输入问题',fc=WHITE,ec=MID,fontsize=13)
    add_box(ax,3.6,3.0,2.8,1.0,'任务路由：single / multi / code',fc='#EEF4FB',ec=BLUE,fontsize=13)
    add_box(ax,7.2,4.4,2.4,0.9,'预算充足',fc='#FFF9F0',ec=GOLD,fontsize=12.5)
    add_box(ax,7.2,1.6,2.4,0.9,'预算紧张',fc='#FFF7F5',ec=RED,fontsize=12.5)
    add_box(ax,10.5,4.25,3.2,1.2,'允许升级：有限检索 + 事实记忆',fc='#F8FBFF',ec=TEAL,fontsize=12.5)
    add_box(ax,10.5,1.45,3.2,1.2,'尽快停止：保持短答与低代价',fc='#F8FAFC',ec='#AAB7C4',fontsize=12.5)
    arrow(ax,3.0,3.5,3.6,3.5)
    arrow(ax,6.4,3.5,7.2,4.85,color=GOLD)
    arrow(ax,6.4,3.5,7.2,2.05,color=RED)
    arrow(ax,9.6,4.85,10.5,4.85,color=TEAL)
    arrow(ax,9.6,2.05,10.5,2.05,color=GRAY)
    savefig(fig,'fig4_2_routing_budget')


def fig4_path_comparison():
    stages = ['route','retrieve','check','escalate','guard','answer']
    depth = {'Single-doc':3.2,'Multi-doc':4.6,'Code':5.4}
    ypos = {'Single-doc':2.6,'Multi-doc':1.6,'Code':0.6}
    fig, ax = plt.subplots(figsize=(11.5,3.8))
    ax.set_xlim(-0.25,5.25); ax.set_ylim(0,3.5)
    for i,s in enumerate(stages):
        ax.axvline(i, color=GRID, lw=0.8, zorder=0)
    colors = {'Single-doc':BLUE,'Multi-doc':TEAL,'Code':PURPLE}
    for name, y in ypos.items():
        d = depth[name]
        xs = np.linspace(0,d-1, int(d))
        ys = np.repeat(y, len(xs))
        ax.plot(xs, ys, color=colors[name], lw=2.2, marker='o', ms=6)
        ax.text(-0.15, y, name, ha='right', va='center', fontproperties=FPB, fontsize=12, color=colors[name])
    ax.set_xticks(range(len(stages)), stages)
    ax.set_yticks([])
    clean(ax, grid=None)
    savefig(fig,'fig4_3_task_path_comparison')


def fig4_budget_logic():
    fig, ax = plt.subplots(figsize=(11.2,4.2))
    ax.set_xlim(0,10); ax.set_ylim(0,7); ax.axis('off')
    add_box(ax,0.6,4.8,2.0,0.9,'新增证据?',fc=WHITE,ec=MID,fontsize=13)
    add_box(ax,3.2,4.8,2.1,0.9,'答案是否收束?',fc=WHITE,ec=MID,fontsize=13)
    add_box(ax,5.9,4.8,2.1,0.9,'预算是否仍值得?',fc='#FFF9F0',ec=GOLD,fontsize=13)
    add_box(ax,8.3,5.25,1.2,0.7,'继续升级',fc='#F8FBFF',ec=TEAL,fontsize=11.5)
    add_box(ax,8.3,4.15,1.2,0.7,'提前停止',fc='#F8FAFC',ec='#AAB7C4',fontsize=11.5)
    add_box(ax,8.3,3.05,1.2,0.7,'输出答案',fc='#F7FAF8',ec=GREEN,fontsize=11.5)
    arrow(ax,2.6,5.25,3.2,5.25)
    arrow(ax,5.3,5.25,5.9,5.25)
    arrow(ax,8.0,5.25,8.3,5.6,color=TEAL)
    arrow(ax,8.0,5.25,8.3,4.5,color=GRAY)
    arrow(ax,4.25,4.8,8.3,3.4,color=GREEN,cs='arc3,rad=-0.15')
    savefig(fig,'fig4_4_budget_logic')


def fig4_recovery_timeline():
    events = [
        ('旧分片在 18/170 停滞', 0.6, RED),
        ('定位为样本级 stall\n而非坏样本', 2.1, BLUE),
        ('增加 600s 样本级超时\n+ 持久 worker', 3.9, TEAL),
        ('优先重启 retry\_pending 分片', 5.4, GOLD),
        ('2026-04-16 12:42\nguardian 恢复运行', 7.1, GREEN),
        ('2026-04-17 01:30\n修复 2 条 baseline 行', 9.2, PURPLE),
        ('formal 报告成功落盘', 11.0, NAVY)
    ]
    fig, ax = plt.subplots(figsize=(12,3.6))
    ax.set_xlim(0,12); ax.set_ylim(0,1); ax.axis('off')
    ax.hlines(0.5,0.5,11.5,color='#AAB7C4',lw=1.8)
    for label, x, c in events:
        ax.scatter([x],[0.5],s=80,color=c,zorder=3)
        ax.vlines(x,0.5,0.82 if int(x*10)%2 else 0.18,color=c,lw=1.3)
        y = 0.85 if int(x*10)%2 else 0.15
        va = 'bottom' if y>0.5 else 'top'
        txt = ax.text(x,y,label,ha='center',va=va,fontproperties=FP,fontsize=11.2)
    savefig(fig,'fig4_5_recovery_timeline')


def fig4_guardrail_stack():
    fig, ax = plt.subplots(figsize=(11.3,4.0))
    ax.set_xlim(0,10); ax.set_ylim(0,8); ax.axis('off')
    layers = [
        ('结果可信度边界\nsingle-seed / anchor baseline / formal hygiene', '#F8FAFC', '#94A3B8'),
        ('运行恢复层\nguardian restart / retry priority / partial shard reuse', '#EEF4FB', BLUE),
        ('执行保护层\nsample timeout / persistent worker / fallback result', '#F0FAF7', TEAL),
        ('观测层\nper-sample start-done log / backend-mode checks', '#FFF9F0', GOLD),
    ]
    y=0.8
    for txt, fc, ec in layers:
        add_box(ax,1.2,y,7.6,1.35,txt,fc=fc,ec=ec,fontsize=13)
        y += 1.65
    savefig(fig,'fig4_6_guardrail_stack')


def fig5_main_results():
    fig, axs = plt.subplots(1,2,figsize=(11.6,4.2), gridspec_kw={'width_ratios':[1,2.1]})
    vals = overall.set_index('label')['f1']
    colors=[BLUE,TEAL]
    axs[0].bar(vals.index, vals.values, color=colors, width=0.55)
    for i,v in enumerate(vals.values):
        axs[0].text(i, v+0.01, f'{v:.4f}', ha='center', va='bottom', fontproperties=FP)
    axs[0].set_ylabel('Overall F1')
    axs[0].set_ylim(0, max(vals.values) * 1.18)
    clean(axs[0],'y')
    wide = task.pivot(index='task', columns='method', values='f1').loc[task_display_order]
    x = np.arange(len(wide))
    bw = 0.32
    axs[1].bar(x-bw/2, wide[baseline].values, width=bw, color=BLUE, label='Baseline')
    axs[1].bar(x+bw/2, wide[agent].values, width=bw, color=TEAL, label='Task-routed')
    for i,(b,a) in enumerate(zip(wide[baseline].values, wide[agent].values)):
        axs[1].text(i-bw/2,b+0.012,f'{b:.4f}',ha='center',va='bottom',fontsize=10,fontproperties=FP)
        axs[1].text(i+bw/2,a+0.012,f'{a:.4f}',ha='center',va='bottom',fontsize=10,fontproperties=FP)
    axs[1].set_xticks(x, [task_map_short[t] for t in task_display_order])
    axs[1].set_ylabel('Task F1')
    axs[1].set_ylim(0, max(wide[baseline].max(), wide[agent].max()) * 1.14)
    axs[1].legend(frameon=False, prop=FP)
    clean(axs[1],'y')
    fig.tight_layout()
    savefig(fig,'fig5_1_main_results')


def fig5_cost_tradeoff():
    fig, ax = plt.subplots(figsize=(6.6,5.0))
    x = overall['p95_latency_ms']/1000
    y = overall['f1']
    cols=[BLUE,TEAL]
    ax.scatter(x,y,s=70,color=cols,zorder=3)
    ax.annotate('', xy=(x.iloc[1], y.iloc[1]), xytext=(x.iloc[0], y.iloc[0]), arrowprops=dict(arrowstyle='->', color=GRAY, lw=1.8))
    for i,row in overall.iterrows():
        ax.text(row['p95_latency_ms']/1000+0.5, row['f1']+0.005, row['label'], fontproperties=FP, fontsize=11)
    ax.text((x.iloc[0]+x.iloc[1])/2+0.4,(y.iloc[0]+y.iloc[1])/2+0.005,'收益伴随更高尾时延',fontproperties=FP,fontsize=10.5,color=GRAY)
    ax.set_xlabel('P95 latency (s)')
    ax.set_ylabel('Overall F1')
    x_pad = max(1.2, (x.max() - x.min()) * 0.25)
    y_pad = max(0.03, (y.max() - y.min()) * 0.35)
    ax.set_xlim(x.min() - x_pad, x.max() + x_pad)
    ax.set_ylim(max(0, y.min() - y_pad), y.max() + y_pad)
    clean(ax,'both')
    savefig(fig,'fig5_2_cost_tradeoff')


def fig5_task_delta():
    wide = task.pivot(index='task', columns='method', values='f1').loc[task_display_order]
    delta = wide[agent]-wide[baseline]
    fig, ax = plt.subplots(figsize=(9,3.8))
    y = np.arange(len(delta))
    colors = [RED if v<0 else TEAL for v in delta]
    ax.barh(y, delta.values, color=colors, height=0.55)
    ax.axvline(0,color='#AAB7C4',lw=1.1)
    for yi,v in zip(y,delta.values):
        ax.text(v + (0.005 if v>=0 else -0.005), yi, f'{v:+.4f}', va='center', ha='left' if v>=0 else 'right', fontproperties=FP)
    ax.set_yticks(y,[task_map_short[t] for t in task_display_order])
    ax.set_xlabel('Δ F1 (task-routed - baseline)')
    clean(ax,'x')
    ax.invert_yaxis()
    savefig(fig,'fig5_3_task_delta')


def fig5_latency_profile():
    fig, ax = plt.subplots(figsize=(8.6,3.6))
    metrics_names=['P50','P95']
    base=[overall.iloc[0]['p50_latency_ms']/1000, overall.iloc[0]['p95_latency_ms']/1000]
    ag=[overall.iloc[1]['p50_latency_ms']/1000, overall.iloc[1]['p95_latency_ms']/1000]
    y=np.array([1,0])
    for yi,b,a in zip(y,base,ag):
        ax.plot([b,a],[yi,yi],color='#B8C4CF',lw=2.2)
        ax.scatter([b],[yi],color=BLUE,s=55,zorder=3)
        ax.scatter([a],[yi],color=TEAL,s=55,zorder=3)
        ax.text(b-0.35, yi+0.1, f'{b:.2f}s', ha='right', fontproperties=FP, fontsize=10.5)
        ax.text(a+0.35, yi+0.1, f'{a:.2f}s', ha='left', fontproperties=FP, fontsize=10.5)
    ax.set_yticks(y, metrics_names)
    ax.set_xlabel('Latency (s)')
    ax.legend(handles=[Line2D([0],[0],marker='o',color='w',markerfacecolor=BLUE,label='Baseline',markersize=8),Line2D([0],[0],marker='o',color='w',markerfacecolor=TEAL,label='Task-routed',markersize=8)],frameon=False,prop=FP,loc='lower right')
    clean(ax,'x')
    savefig(fig,'fig5_4_latency_profile')


def fig5_operational_overheads():
    fig, axs = plt.subplots(1,5, figsize=(12.8,3.5))
    cols = [('avg_steps','Steps'),('avg_retrieval','Retrievals'),('avg_prompt_tokens_total','Prompt tokens'),('avg_completion_tokens_total','Completion tokens'),('oom_count','OOM')]
    for ax,(col,title) in zip(axs,cols):
        vals = overall[col].values
        ax.bar([0,1], vals, color=[BLUE,TEAL], width=0.6)
        for i,v in enumerate(vals):
            fmt = '{:.2f}' if col!='oom_count' else '{:.0f}'
            ax.text(i,v+(max(vals)*0.04 if max(vals)>0 else 0.1),fmt.format(v),ha='center',va='bottom',fontsize=9.5,fontproperties=FP)
        ax.set_xticks([0,1], ['Base','Task'])
        ax.set_title(title, fontproperties=FPB, fontsize=11)
        clean(ax,'y')
    fig.tight_layout()
    savefig(fig,'fig5_5_operational_overheads')


def fig5_weighted_contribution():
    tmp = task[['task','n_samples','f1','method']].pivot(index='task', columns='method', values='f1').loc[task_display_order]
    n = task.drop_duplicates('task').set_index('task')['n_samples'].loc[task_display_order]
    delta = (tmp[agent]-tmp[baseline]) * n / n.sum()
    fig, ax = plt.subplots(figsize=(9.2,4.3))
    start = 0
    xs=np.arange(len(delta)+1)
    colors=[RED if v<0 else TEAL for v in delta.values] + [NAVY]
    cum = 0
    for i,(name,v) in enumerate(delta.items()):
        ax.bar(i, v, bottom=cum if v>=0 else cum+v, color=colors[i], width=0.62)
        y = cum + v if v>=0 else cum
        ax.text(i, y + (0.004 if v>=0 else -0.004), f'{v:+.4f}', ha='center', va='bottom' if v>=0 else 'top', fontproperties=FP, fontsize=10.5)
        cum += v
    ax.bar(len(delta), cum, color=NAVY, width=0.62)
    ax.text(len(delta), cum+0.005, f'{cum:+.4f}', ha='center', va='bottom', fontproperties=FP, fontsize=10.5)
    ax.axhline(0,color='#AAB7C4',lw=0.9)
    ax.set_xticks(xs, [task_map_short[t] for t in task_display_order]+['Overall'])
    ax.set_ylabel('Weighted contribution to Δ overall F1')
    clean(ax,'y')
    savefig(fig,'fig5_6_weighted_contribution')


def fig5_case_matrix():
    cards = [
        ('多文档正例','MuSiQue / HotpotQA\n跨文档对齐后更容易收束到最终实体或年份', '#F8FBFF', BLUE),
        ('代码正例','LCC / RepoBench-P\n从无效输出推进到目标代码区域附近', '#F0FAF7', TEAL),
        ('英文短答反例','single\_doc 数值抽取\n原可直接命中，却被解释性输出带偏', '#FFF7F5', RED),
        ('中文短答反例','single\_doc 中文短答\n额外检索引入噪声，短答案失焦', '#FFF7F5', RED),
    ]
    fig, ax = plt.subplots(figsize=(11.5,5.6))
    ax.set_xlim(0,12); ax.set_ylim(0,8); ax.axis('off')
    coords=[(0.8,4.4),(6.2,4.4),(0.8,1.0),(6.2,1.0)]
    for (title,body,fc,ec),(x,y) in zip(cards,coords):
        add_box(ax,x,y,4.8,2.2,f'{title}\n{body}',fc=fc,ec=ec,fontsize=13)
    savefig(fig,'fig5_7_case_matrix')


def fig5_task_frontier():
    wide_f1 = task.pivot(index='task', columns='method', values='f1').loc[task_display_order]
    wide_p95 = task.pivot(index='task', columns='method', values='p95_latency_ms').loc[task_display_order]/1000
    fig, ax = plt.subplots(figsize=(6.8,5.0))
    colors={'single_doc_qa':RED,'multi_doc_qa':TEAL,'code_qa':PURPLE}
    for t in task_display_order:
        bx, by = wide_p95.loc[t, baseline], wide_f1.loc[t, baseline]
        ax.scatter([bx],[by],s=46,color=BLUE,zorder=3)
        ax.scatter([wide_p95.loc[t, agent]],[wide_f1.loc[t, agent]],s=60,color=colors[t],zorder=4)
        ax.annotate('', xy=(wide_p95.loc[t, agent], wide_f1.loc[t, agent]), xytext=(bx, by), arrowprops=dict(arrowstyle='->', lw=1.6, color=colors[t]))
        ax.text(wide_p95.loc[t, agent]+0.4, wide_f1.loc[t, agent], task_map_short[t], fontproperties=FP, fontsize=10.5, color=colors[t])
    ax.set_xlabel('P95 latency (s)')
    ax.set_ylabel('Task F1')
    clean(ax,'both')
    savefig(fig,'fig5_8_task_frontier')


def fig5_task_burden_heatmap():
    burden_cols=['avg_steps','avg_retrieval','avg_prompt_tokens_total','avg_completion_tokens_total','p95_latency_ms','oom_count']
    d = task.pivot(index='task', columns='method', values=burden_cols)
    ratio = pd.DataFrame(index=task_display_order, columns=burden_cols)
    for c in burden_cols:
        base = d[(c, baseline)]
        ag = d[(c, agent)]
        ratio[c] = ag / base.replace(0,np.nan)
        if c == 'oom_count':
            ratio[c] = ag.replace(0,np.nan)
    ratio = ratio.loc[task_display_order]
    mat = ratio[['avg_steps','avg_retrieval','avg_prompt_tokens_total','avg_completion_tokens_total','p95_latency_ms','oom_count']].astype(float).fillna(0).values
    fig, ax = plt.subplots(figsize=(8.8,4.4))
    im = ax.imshow(mat, cmap='Blues', aspect='auto')
    ax.set_xticks(range(mat.shape[1]), ['steps','retrieval','prompt','completion','p95','OOM'])
    ax.set_yticks(range(mat.shape[0]), [task_map_short[t] for t in task_display_order])
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            txt = f'{mat[i,j]:.2f}×' if j<5 else f'{int(mat[i,j])}'
            ax.text(j,i,txt,ha='center',va='center',fontproperties=FP,fontsize=10,color=DARK)
    clean(ax,None)
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.03)
    savefig(fig,'fig5_9_task_burden_heatmap')


def fig5_high_value_combo():
    wide = task.pivot(index='task', columns='method', values='f1')
    base_combo = wide.loc[['multi_doc_qa','code_qa'], baseline].mean()
    agent_combo = wide.loc[['multi_doc_qa','code_qa'], agent].mean()
    base_over = overall.loc[overall['method']==baseline,'f1'].iloc[0]
    agent_over = overall.loc[overall['method']==agent,'f1'].iloc[0]
    fig, axs = plt.subplots(1,2,figsize=(9.8,4.0))
    axs[0].bar([0,1], [base_over, agent_over], color=[BLUE,TEAL], width=0.58)
    axs[0].set_xticks([0,1], ['Overall base','Overall task'])
    axs[0].set_ylabel('F1')
    axs[0].set_ylim(0, max(base_over, agent_over) * 1.16)
    axs[1].bar([0,1], [base_combo, agent_combo], color=[BLUE,TEAL], width=0.58)
    axs[1].set_xticks([0,1], ['High-value base','High-value task'])
    axs[1].set_ylabel('Macro F1')
    axs[1].set_ylim(0, max(base_combo, agent_combo) * 1.16)
    for ax, vals in zip(axs, [[base_over, agent_over],[base_combo, agent_combo]]):
        for i,v in enumerate(vals):
            ax.text(i,v+0.008,f'{v:.4f}',ha='center',va='bottom',fontproperties=FP,fontsize=10)
        clean(ax,'y')
    fig.tight_layout()
    savefig(fig,'fig5_10_high_value_combo')


def fig5_error_histogram():
    fig, ax = plt.subplots(figsize=(7.8,4.4))
    bins=np.linspace(0,0.4,17)
    for m,c in [(baseline,BLUE),(agent,TEAL)]:
        vals = errors.loc[errors['method']==m,'f1']
        ax.hist(vals,bins=bins,alpha=0.45,color=c,label=label_map[m],density=True,edgecolor='white')
    ax.set_xlabel('Error-case token-level F1')
    ax.set_ylabel('Density')
    ax.legend(frameon=False, prop=FP)
    clean(ax,'y')
    savefig(fig,'fig5_11_error_histogram')


def fig5_error_boxplot():
    plot_df = errors.dropna(subset=['task']).copy()
    order = ['Single-doc','Multi-doc','Code']
    fig, ax = plt.subplots(figsize=(8.8,4.4))
    positions=[]; data=[]; colors=[]; labels=[]; idx=1
    for t in order:
        for m,c in [('Baseline',BLUE),('Task-routed',TEAL)]:
            vals = plot_df[(plot_df['task_label']==t)&(plot_df['method_label']==m)]['f1'].values
            data.append(vals)
            positions.append(idx)
            colors.append(c)
            labels.append(f'{t}\n{m}')
            idx += 1
        idx += 0.35
    bp = ax.boxplot(data, positions=positions, widths=0.55, patch_artist=True, showfliers=False, medianprops=dict(color='white', linewidth=1.4))
    for patch,c in zip(bp['boxes'], colors):
        patch.set_facecolor(c); patch.set_alpha(0.85); patch.set_edgecolor('white')
    ax.set_xticks(positions, labels)
    ax.set_ylabel('Error-case F1')
    clean(ax,'y')
    savefig(fig,'fig5_12_error_boxplot')


def fig5_error_heatmap():
    ct = errors.groupby(['dataset','method_label']).size().unstack(fill_value=0)
    ds_order = [k for k,_ in ct.sum(axis=1).sort_values(ascending=False).items()]
    ct = ct.loc[ds_order, ['Baseline','Task-routed']]
    fig, ax = plt.subplots(figsize=(6.6,5.2))
    mat = ct.values
    im=ax.imshow(mat,cmap='Blues',aspect='auto')
    ax.set_xticks(range(2), ['Baseline','Task-routed'])
    ax.set_yticks(range(len(ds_order)), ds_order)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            ax.text(j,i,str(int(mat[i,j])),ha='center',va='center',fontproperties=FP,fontsize=10)
    clean(ax,None)
    fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03)
    savefig(fig,'fig5_13_error_heatmap')


def fig5_error_ecdf():
    fig, ax = plt.subplots(figsize=(7.5,4.2))
    for m,c in [(baseline,BLUE),(agent,TEAL)]:
        vals = np.sort(errors.loc[errors['method']==m,'f1'].values)
        y = np.arange(1,len(vals)+1)/len(vals)
        ax.plot(vals,y,color=c,lw=2.0,label=label_map[m])
    ax.set_xlabel('Error-case F1 threshold')
    ax.set_ylabel('ECDF')
    ax.legend(frameon=False, prop=FP, loc='lower right')
    clean(ax,'both')
    savefig(fig,'fig5_14_error_ecdf')


for fn in [fig1_problem_tension, fig2_gap_matrix, fig3_eval_scope, fig4_workflow, fig4_routing_budget, fig4_path_comparison, fig4_budget_logic, fig4_recovery_timeline, fig4_guardrail_stack, fig5_main_results, fig5_cost_tradeoff, fig5_task_delta, fig5_latency_profile, fig5_operational_overheads, fig5_weighted_contribution, fig5_case_matrix, fig5_task_frontier, fig5_task_burden_heatmap, fig5_high_value_combo, fig5_error_histogram, fig5_error_boxplot, fig5_error_heatmap, fig5_error_ecdf]:
    fn()
print('generated', len(list(FIG.glob('*.png'))), 'pngs')
