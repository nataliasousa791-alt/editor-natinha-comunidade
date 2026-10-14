"""Vigia do Drive: video que cair em ROBO_CINEMATIC_ENTRADA vira YouTube 16:9 (limpo + B-roll) e 3 cortes 9:16.
Um video por vez. Resultado em ROBO_CINEMATIC_SAIDA\<nome>\. Nada e publicado; nao toca em 'prontos' (postador) nem 'entrada'."""
import json, os, shutil, subprocess, sys, time, glob, re

DRIVE = r"G:\Meu Drive\Editor Natinha"
ENT = os.path.join(DRIVE, "ROBO_CINEMATIC_ENTRADA")
SAI = os.path.join(DRIVE, "ROBO_CINEMATIC_SAIDA")
ROBO = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(ROBO, ".venv", "Scripts", "python.exe")
LOCAL = os.path.join(ROBO, "entrada_local")
REG = os.path.join(ROBO, "vigia_feitos.json")
LOG = os.path.join(ROBO, "vigia.log")
EXT = (".mp4", ".mov", ".mkv", ".m4v")


def log(m):
    linha = f"[{time.strftime('%d/%m %H:%M:%S')}] {m}"
    open(LOG, "a", encoding="utf-8").write(linha + "\n")


def status(txt):
    try:
        open(os.path.join(SAI, "_STATUS_DO_ROBO.txt"), "w", encoding="utf-8").write(
            f"Atualizado em {time.strftime('%d/%m/%Y %H:%M')}\n\n{txt}\n")
    except Exception as e:
        log(f"status falhou: {e}")


def feitos():
    return json.load(open(REG, encoding="utf-8")) if os.path.exists(REG) else {}


def estavel(p):
    """Arquivo terminou de sincronizar: tamanho > 0 e igual por 60 s."""
    try:
        a = os.path.getsize(p); time.sleep(60); return a > 0 and a == os.path.getsize(p)
    except OSError:
        return False


def processar(arq):
    base = os.path.splitext(os.path.basename(arq))[0]
    nome = re.sub(r"[^A-Za-z0-9_-]+", "_", base)[:40].strip("_") + time.strftime("_%d%m%H%M")
    os.makedirs(LOCAL, exist_ok=True)
    loc = os.path.join(LOCAL, nome + os.path.splitext(arq)[1])
    status(f"COPIANDO do Drive: {os.path.basename(arq)}")
    shutil.copy2(arq, loc)                                           # trabalha numa copia local (Drive pode oscilar)
    status(f"EDITANDO: {os.path.basename(arq)}\nVersao YouTube + 3 cortes verticais. Leva ~2h a 3h para video de 10 min.\nNao desligue o PC.")
    log(f"inicio {arq} -> job {nome}")
    with open(os.path.join(ROBO, "jobs", f"_vigia_{nome}.out"), "w", encoding="utf-8") as out:
        r = subprocess.run([PY, "-X", "utf8", "robo.py", loc, "--saidas", "yt,yt_broll,cortes", "--cortes", "3", "--nome", nome],
                           cwd=ROBO, stdout=out, stderr=subprocess.STDOUT)
    dest = os.path.join(SAI, nome); os.makedirs(dest, exist_ok=True)
    copiados = []
    for f in glob.glob(os.path.join(ROBO, "jobs", nome, "**", "*.*"), recursive=True):
        if re.search(r"_(CORTE\d_9x16|YOUTUBE_LIMPO_16x9|YOUTUBE_BROLL_16x9)\.(mp4|srt)$", f):
            shutil.copy2(f, dest); copiados.append(os.path.basename(f))
    ok = r.returncode == 0 and any(c.endswith(".mp4") for c in copiados)
    log(f"fim {nome} codigo {r.returncode} copiados {copiados}")
    return ok, nome, copiados


def main():
    for p in (ENT, SAI): os.makedirs(p, exist_ok=True)
    log("vigia iniciado")
    status("PARADO, esperando video.\nColoque o video bruto na pasta ROBO_CINEMATIC_ENTRADA.")
    while True:
        reg = feitos()
        novos = [f for f in sorted(glob.glob(os.path.join(ENT, "*")), key=os.path.getmtime)
                 if f.lower().endswith(EXT) and f"{os.path.basename(f)}|{os.path.getsize(f)}" not in reg]
        for f in novos[:1]:
            chave = f"{os.path.basename(f)}|{os.path.getsize(f)}"
            if not estavel(f): continue
            try:
                ok, nome, cop = processar(f)
            except Exception as e:
                ok, nome, cop = False, "", []; log(f"ERRO {f}: {e}")
            reg[chave] = dict(job=nome, ok=ok, quando=time.strftime("%d/%m/%Y %H:%M"), arquivos=cop)
            json.dump(reg, open(REG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            if ok:
                status(f"PRONTO: {os.path.basename(f)}\nVideos na pasta ROBO_CINEMATIC_SAIDA\\{nome}\n"
                       "(PREVIA para aprovacao: nada foi publicado)\n\nPARADO, esperando o proximo video.")
            else:
                status(f"FALHOU: {os.path.basename(f)}\nAvise o Claude: log em robo\\jobs\\_vigia_{nome}.out\n\n"
                       "Para tentar de novo, renomeie o video e coloque na ENTRADA outra vez.")
        time.sleep(60)


if __name__ == "__main__":
    main()
