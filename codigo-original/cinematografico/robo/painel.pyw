"""Painel do Robô Editor Natinha — escolhe o vídeo, marca as saídas, clica em EDITAR. Sem Claude.
v2: a janela nunca congela (o robô roda separado, em prioridade baixa, e a janela só lê o arquivo de log)."""
import ctypes, os, subprocess, sys, tkinter as tk
from tkinter import filedialog, ttk

R = os.path.dirname(os.path.abspath(__file__)); JOBS = os.path.join(R, "jobs"); os.makedirs(JOBS, exist_ok=True)
LOG, PIDF = os.path.join(JOBS, "_painel.log"), os.path.join(JOBS, "_painel.pid")
BG, CARD, TXT, CINZA, AMBAR = "#121316", "#1C1D21", "#F5F3EE", "#A3A7AF", "#E8833A"

def vivo(pid):
    k = ctypes.windll.kernel32; h = k.OpenProcess(0x1000, False, pid)
    if not h: return False
    c = ctypes.c_ulong(); k.GetExitCodeProcess(h, ctypes.byref(c)); k.CloseHandle(h); return c.value == 259

def pid_atual():
    try: p = int(open(PIDF).read().strip()); return p if vivo(p) else None
    except Exception: return None

j = tk.Tk(); j.title("Robô Editor Natinha"); j.geometry("620x560"); j.configure(bg=BG); j.resizable(False, False)
F = lambda s, w="normal": ("Segoe UI", s, w)
tk.Label(j, text="ROBÔ EDITOR", font=F(11, "bold"), fg=CINZA, bg=BG).pack(anchor="w", padx=28, pady=(22, 0))
tk.Label(j, text="Natinha", font=("Georgia", 30, "bold italic"), fg=AMBAR, bg=BG).pack(anchor="w", padx=28)

caixa = tk.Frame(j, bg=CARD); caixa.pack(fill="x", padx=28, pady=14)
video = tk.StringVar(value="Nenhum vídeo escolhido")
tk.Label(caixa, textvariable=video, font=F(10), fg=TXT, bg=CARD, wraplength=420, justify="left").pack(side="left", padx=14, pady=14)
def escolher():
    f = filedialog.askopenfilename(filetypes=[("Vídeos", "*.mp4 *.mov *.mkv *.m4v")])
    if f: video.set(f)
tk.Button(caixa, text="Escolher vídeo", command=escolher, font=F(10, "bold"), bg=AMBAR, fg="#111", relief="flat",
          padx=12, pady=6, cursor="hand2").pack(side="right", padx=14)

op = tk.Frame(j, bg=BG); op.pack(fill="x", padx=28)
s_yt, s_ytb, s_ct = tk.BooleanVar(value=True), tk.BooleanVar(value=True), tk.BooleanVar(value=True)
for txt, var in (("YouTube limpo (16:9)", s_yt), ("YouTube com B-roll (16:9)", s_ytb), ("Cortes TikTok/Reels (9:16)", s_ct)):
    tk.Checkbutton(op, text=txt, variable=var, font=F(10), fg=TXT, bg=BG, selectcolor=CARD, activebackground=BG,
                   activeforeground=TXT).pack(anchor="w")
lin = tk.Frame(op, bg=BG); lin.pack(anchor="w", pady=(6, 0))
tk.Label(lin, text="Quantidade de cortes:", font=F(10), fg=CINZA, bg=BG).pack(side="left")
n_cortes = ttk.Combobox(lin, values=[1, 2, 3], width=3, state="readonly"); n_cortes.set(2); n_cortes.pack(side="left", padx=8)

log = tk.Text(j, height=11, bg=CARD, fg=CINZA, font=("Consolas", 9), relief="flat", padx=10, pady=8)
log.pack(fill="both", padx=28, pady=12)
status = tk.StringVar(value="Pronto.")
tk.Label(j, textvariable=status, font=F(10, "bold"), fg=AMBAR, bg=BG).pack(anchor="w", padx=28)

def rodar():
    if pid_atual(): status.set("Já está editando — aguarde terminar."); return
    v = video.get()
    if not os.path.isfile(v): status.set("Escolha um vídeo primeiro."); return
    saidas = ",".join(n for n, b in (("yt", s_yt), ("yt_broll", s_ytb), ("cortes", s_ct)) if b.get())
    if not saidas: status.set("Marque pelo menos uma saída."); return
    py = os.path.join(os.path.dirname(sys.executable), "python.exe")
    out = open(LOG, "w", encoding="utf-8")
    p = subprocess.Popen([py, "-u", "robo.py", v, "--saidas", saidas, "--cortes", n_cortes.get()], cwd=R,
                         stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                         creationflags=0x08000000 | 0x00004000)  # sem janela + prioridade baixa (PC não engasga)
    open(PIDF, "w").write(str(p.pid)); log.delete("1.0", "end"); pos[0] = 0

pos, rodava = [0], [False]
def atualizar():  # roda na própria janela a cada 1 s — nunca trava
    try:
        if os.path.isfile(LOG):
            with open(LOG, encoding="utf-8", errors="replace") as f:
                f.seek(pos[0]); novo = f.read(); pos[0] = f.tell()
            if novo:
                log.insert("end", novo); log.see("end")
                if float(log.index("end")) > 600: log.delete("1.0", "200.0")
        ativo = bool(pid_atual())
        if ativo: status.set("Editando… pode minimizar. Feche o Chrome/Edge para ir mais rápido."); bt.config(state="disabled")
        elif rodava[0]:
            fim = log.get("end-4l", "end").lower()
            status.set("Parou com erro — clique EDITAR de novo, ele continua de onde parou." if ("erro" in fim or "traceback" in fim)
                       else "Pronto! Clique em 'Abrir resultados'.")
            bt.config(state="normal")
        rodava[0] = ativo
    except Exception as e:
        status.set(f"Aviso: {e}")
    j.after(1000, atualizar)

bot = tk.Frame(j, bg=BG); bot.pack(fill="x", padx=28, pady=12)
bt = tk.Button(bot, text="EDITAR", command=rodar, font=F(12, "bold"), bg=AMBAR, fg="#111", relief="flat", padx=26, pady=8, cursor="hand2")
bt.pack(side="left")
tk.Button(bot, text="Abrir resultados", command=lambda: os.startfile(JOBS), font=F(10),
          bg=CARD, fg=TXT, relief="flat", padx=14, pady=8, cursor="hand2").pack(side="left", padx=10)
j.after(300, atualizar)
j.mainloop()
