"""Resumo da prova (somente leitura dos jobs) + folha de quadros de cada MP4 final."""
import json, os, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
R = os.path.dirname(os.path.abspath(__file__))
for job in ("teste1_0310-0450", "teste2_0520-0712"):
    J = os.path.join(R, "jobs", job); C = os.path.join(J, "corte1")
    p, q = json.load(open(os.path.join(C, "plano.json"), encoding="utf-8")), json.load(open(os.path.join(C, "qa.json"), encoding="utf-8"))
    cj = json.load(open(os.path.join(J, "cortes.json"), encoding="utf-8")); e = cj["escolhidos"][0]; F = cj["frases"]
    print(f"\n### {job}  método={cj['metodo']}  dur={p['corte']['duracao']}s  trecho_bruto={p['corte']['trecho_bruto']}  tema={e.get('tema')}")
    print("  INÍCIO:", F[e["a"]]["texto"][:110]); print("  FIM:   ", F[e["b"]]["texto"][:110])
    for c in p["cenas"]:
        t = c.get("texto") or [w["w"] for w in c.get("frase", c.get("palavras", []))]
        print(f"  {c['tipo']:10s} {c['ini']:6.2f}-{c['fim']:6.2f} | {' '.join(t)[:60]} | {c.get('asset', {}).get('id', '')} {c.get('gatilho', {}).get('palavra', '')}")
    print("  QA:", q["formato"], "| legendas", q["legendas"]["conferidas"], "/", q["legendas"]["total"], "mediana", q["legendas"]["mediana_s"],
          "p90", q["legendas"]["p90_s"], "| congel", q["congelamento_max_quadros"], "| pretas", q["telas_pretas"], "| repetidos", q["assets"]["repetidos"],
          "| render", q.get("tempo_render_s"), "s")
    mp4 = os.path.join(C, f"{job}_corte1_PREVIA.mp4"); dur = q["formato"]["dur"]
    ts = [round(dur * k / 9, 2) for k in range(1, 9)]
    sel = "+".join(f"eq(n\\,{round(t * 30)})" for t in ts)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-vf", f"select='{sel}',scale=180:320,tile=8x1", "-fps_mode", "passthrough",
                    "-frames:v", "1", os.path.join(C, "folha_final.jpg")])
    print("  folha:", ts)
