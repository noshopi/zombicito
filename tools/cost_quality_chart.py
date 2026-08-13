import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

models = [
    # nombre, costo entrada USD/M, costo salida USD/M, score diseño videojuegos (0-100), nota
    ("deepseek-v4-flash",      0.27,  1.10, 82, "Bajo costo / muy bueno"),
    ("deepseek-v4",            0.60,  2.40, 91, "Buen balance"),
    ("deepseek-v4-thinking",   0.60,  2.40, 95, "Mejor calidad, más lento"),
    ("deepseek-v4-nano",       0.05,  0.20, 55, "Ultra barato, simple"),
    ("deepseek-v4-pro",        1.20,  4.80, 97, "Calidad máxima"),
]

fig, ax = plt.subplots(figsize=(11, 6.5))
fig.patch.set_facecolor("#14171f")
ax.set_facecolor("#1c212b")

x = [m[1] for m in models]
y = [m[3] for m in models]
sizes = [m[2] * 260 for m in models]
colors = ["#3aa0ff", "#58c46b", "#ffb03a", "#9aa0aa", "#d95bd9"]

for (name, ci, co, score, note), xx, yy, ss, cc in zip(models, x, y, sizes, colors):
    ax.scatter(xx, yy, s=ss, c=cc, alpha=0.9, edgecolors="white", linewidths=1.5, zorder=3)
    ax.annotate(name, (xx, yy), textcoords="offset points", xytext=(14, 6),
                fontsize=11, color="white", fontweight="bold", zorder=4)
    ax.annotate(f"${xx:.2f}", (xx, yy), textcoords="offset points", xytext=(14, -8),
                fontsize=9, color="#aeb6c2")

ax.set_xscale("log")
ax.set_xlim(0.03, 2.5)
ax.set_ylim(40, 105)

ax.set_xlabel("Costo de entrada (USD por 1M tokens) — escala log", color="white", fontsize=12)
ax.set_ylabel("Resultado en diseño de videojuegos (score 0-100)", color="white", fontsize=12)
ax.set_title("Modelos opencode-go: costo vs. resultado en diseño de videojuegos",
             color="white", fontsize=15, fontweight="bold", pad=14)

ax.tick_params(colors="white")
for s in ax.spines.values():
    s.set_color("#3a4250")
ax.grid(color="#3a4250", linestyle="--", linewidth=0.5, alpha=0.4)

handles = [mpatches.Patch(color=cc, label=f"{n} — in ${ci:.2f}/out ${co:.2f} — {sc}/100") for n, ci, co, sc, cc in zip(
    [m[0] for m in models], [m[1] for m in models], [m[2] for m in models], [m[3] for m in models], colors)]
ax.legend(handles=handles, loc="upper left", fontsize=9, framealpha=0.3,
          facecolor="#1c212b", edgecolor="#3a4250", labelcolor="white")

ax.text(0.99, 0.02, "Valores estimados. El tamaño del punto indica el costo de salida.",
        transform=ax.transAxes, ha="right", fontsize=9, color="#8b93a1")

fig.text(0.02, 0.02, "Costo de salida (USD/M): flash $1.10 · v4 $2.40 · thinking $2.40 · nano $0.20 · pro $4.80",
         color="#8b93a1", fontsize=9)

plt.tight_layout(rect=[0, 0.04, 1, 1])
plt.savefig("tools/costo_resultado_opencode_go.png", dpi=130, facecolor=fig.get_facecolor())
print("Guardado: tools/costo_resultado_opencode_go.png")
