import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

fig, ax = plt.subplots(figsize=(12, 7))
ax.set_xlim(0, 12)
ax.set_ylim(0, 7)
ax.axis("off")


def box(x, y, w, h, text, color="#eef2ff", edge="#4f46e5"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02", fc=color, ec=edge, lw=1.5))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=10)


def arrow(x1, y1, x2, y2, text=None, color="#4f46e5"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14, color=color, lw=1.5))
    if text:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.1, text, ha="center", va="bottom", fontsize=8, color="#3730a3")


ax.text(6, 6.5, "库门口异常停留识别系统架构", ha="center", va="center", fontsize=16, fontweight="bold")

box(0.4, 4.8, 2.2, 1.0, "视频源\n摄像头/RTSP", color="#f3f4f6", edge="#6b7280")
box(3.0, 4.5, 3.0, 1.8, "边缘端\n车辆检测\n区域判断\n停留计时\n关键帧抽取\n脱敏压缩", color="#ecfeff", edge="#0891b2")
box(6.4, 4.5, 3.0, 1.8, "云端分析\n事件管理\n异常停留分类\nVL语义解释\n人工复核\n数据回流", color="#eef2ff", edge="#4f46e5")
box(9.8, 4.8, 2.0, 1.0, "业务闭环\n告警/任务/统计", color="#f0fdf4", edge="#16a34a")

arrow(2.6, 5.3, 3.0, 5.3)
arrow(6.0, 5.3, 6.4, 5.3, "关键帧")
arrow(9.4, 5.3, 9.8, 5.3)

box(1.0, 2.6, 10.0, 1.0, "数据与治理：对象存储 · PostgreSQL · 消息队列 · 权限审计 · 隐私脱敏 · 跨摄像头去重", color="#fff7ed", edge="#f97316")
arrow(7.9, 4.5, 7.9, 3.6, color="#f97316")

box(1.0, 1.2, 4.5, 1.0, "边缘模型：YOLO-Nano / YOLOv8n / MobileNet-SSD", color="#f5f3ff", edge="#7c3aed")
box(5.9, 1.2, 5.1, 1.0, "云端模型：时序Transformer / 3D CNN / Qwen2.5-VL", color="#faf5ff", edge="#a21caf")

arrow(3.25, 2.6, 3.25, 2.2, color="#7c3aed")
arrow(8.45, 2.6, 8.45, 2.2, color="#a21caf")

plt.tight_layout()
plt.savefig("architecture.png", dpi=200, bbox_inches="tight")
