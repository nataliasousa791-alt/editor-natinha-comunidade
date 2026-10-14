"""Orquestra tudo: bruto → transcrição → YouTube → cortes → B-rolls → cortes montados.
Cada etapa grava seus arquivos; se algo falhar, rodar de novo continua de onde parou."""
import json, os, time, traceback
from .util import Progresso, ler_config, probe, usar_versao, VERSOES
from . import transcrever, youtube, cortes, brolls, compor, insercoes, youtube_brolls, capa, vertical


def _j(p):
    return json.load(open(p, encoding="utf-8"))


def processar(pasta):
    pr = Progresso(pasta)
    proj = _j(os.path.join(pasta, "projeto.json"))
    bruto = proj["bruto"]
    log = pr.log
    versao = proj.get("versao") or ler_config(sem_versao=True).get("versao_padrao", "v3.1")
    usar_versao(versao)
    from . import brolls_v2
    brolls_v2.VIDEO_USADAS.clear()
    try:
        pr.set(erro=None, pronto=False)
        log("Versão do editor: " + VERSOES.get(versao, VERSOES["v3.1"])[0])
        if proj.get("tipo") == "vertical":         # entrada_vertical: já é vertical (não gira, não vira YouTube)
            vertical.processar_vertical(pasta, pr, proj)
            pr.etapa("Pronto", 100)
            pr.set(pronto=True)
            if proj.get("exportar_para"):
                exportar(pasta, proj["exportar_para"], log)
            return
        # vídeo gravado na horizontal que chegou "em pé" (celular/WhatsApp/Drive): gira sozinho
        if "girar" not in proj:
            try:
                info = probe(bruto)
                if info["h"] > info["w"] and ler_config().get("girar_vertical_auto", -90):
                    proj["girar"] = int(ler_config().get("girar_vertical_auto", -90))
                    json.dump(proj, open(os.path.join(pasta, "projeto.json"), "w", encoding="utf-8"), ensure_ascii=False)
                    log("O vídeo chegou em pé; girando para a horizontal (dá para mudar nos botões de girar).")
            except Exception as e:
                log(f"(não deu para conferir se o vídeo está deitado: {e})")
        # 1. transcrição do bruto
        f_pal = os.path.join(pasta, "palavras_bruto.json")
        if not os.path.exists(f_pal):
            pr.etapa("Transcrevendo o áudio", 5)
            transcrever.transcrever(bruto, f_pal, log)
        words = _j(f_pal)
        log(f"{len(words)} palavras transcritas")
        # 2. versão YouTube
        f_yt = os.path.join(pasta, "youtube.mp4")
        if not os.path.exists(f_yt):
            f_pal_yt = os.path.join(pasta, "youtube_palavras.json")
            antigas = _j(f_pal_yt) if os.path.exists(f_pal_yt) else None
            pr.etapa("Editando a versão do YouTube", 25)
            youtube.versao_youtube(bruto, words, pasta, log, proj.get("girar", 0))
            if antigas:
                _reajustar_tempos(pasta, antigas, _j(f_pal_yt), log)
        words_yt = _j(os.path.join(pasta, "youtube_palavras.json"))
        trechos = _j(os.path.join(pasta, "youtube_trechos.json"))
        pr.set(youtube=True)
        # 2a. capas para o Test & Compare
        if ler_config().get("youtube_capas", True) and not os.path.exists(os.path.join(pasta, "capa_1.jpg")):
            pr.etapa("Criando as capas do YouTube", 33)
            try:
                capa.gerar(pasta, log)
            except Exception as e:
                log(f"Capas não saíram por enquanto ({e}).")
        f_ex = os.path.join(pasta, "youtube_extra.json")
        extra = _j(f_ex) if os.path.exists(f_ex) else {}
        t_ini = float(extra.get("teaser", 0) or 0) + 1.0
        t_fim = float(extra.get("fim_conteudo", 1e9) or 1e9) - 4.0
        # 2b. imagens (ícones) no vídeo do YouTube — se der erro, segue sem elas
        f_yti = os.path.join(pasta, "youtube_com_imagens.mp4")
        if ler_config().get("insercoes_youtube", True) and not os.path.exists(f_yti):
            pr.etapa("Colocando imagens no vídeo do YouTube", 35)
            info_yt = probe(f_yt)
            lista, extras = [], []
            try:
                lista = insercoes.planejar(words_yt, pasta, log, altura=info_yt["h"])
                lista = [x for x in lista if t_ini <= float(x["tempo"]) <= t_fim]   # nada na prévia nem na tela final
            except Exception as e:
                log(f"Vídeo do YouTube ficou sem cartões por enquanto ({e}).")
            if ler_config().get("youtube_brolls", True):
                pr.etapa("Criando B-rolls do vídeo do YouTube", 38)
                try:
                    extras = youtube_brolls.preparar(words_yt, pasta, lista, log, info_yt["w"], info_yt["h"])
                    extras = [x for x in extras if x["inicio"] >= t_ini + 4 and x["inicio"] + x["dur"] <= t_fim]
                except Exception as e:
                    log(f"Vídeo do YouTube ficou sem B-rolls por enquanto ({e}).")
            try:
                pr.etapa("Juntando tudo no vídeo do YouTube", 42)
                insercoes.aplicar(f_yt, lista, f_yti, log, extras=extras)
            except Exception as e:
                log(f"Vídeo do YouTube ficou sem imagens por enquanto ({e}).")
        # 3. cortes
        f_c = os.path.join(pasta, "cortes.json")
        if not os.path.exists(f_c):
            pr.etapa("Escolhendo os cortes", 45)
            cortes.escolher(words_yt, pasta, log)
        lista = _j(f_c)
        # 4. B-rolls e montagem de cada corte
        for k, ct in enumerate(lista):
            pc = os.path.join(pasta, f"corte_{ct['n']}")
            os.makedirs(pc, exist_ok=True)
            base_pct = 50 + 45 * k / max(1, len(lista))
            f_b = os.path.join(pc, "brolls.json")
            f_out = os.path.join(pc, f"corte_{ct['n']}.mp4")
            novo_plano = False
            if not os.path.exists(f_b):
                pr.etapa(f"Criando B-rolls do corte {ct['n']}", base_pct)
                try:
                    brolls.planejar(words_yt, ct, pc, log)
                    novo_plano = True
                except Exception as e:
                    log(f"Corte {ct['n']} vai sem B-roll por enquanto ({e}). Clique em 'Continuar' depois para tentar de novo.")
            plano = _j(f_b) if os.path.exists(f_b) else []
            # plano novo: desenha tudo de novo (um broll_1.mp4 antigo não serve para a receita nova)
            faltando = (list(range(len(plano))) if novo_plano else
                        [i for i, b in enumerate(plano) if not os.path.exists(os.path.join(pc, b["arquivo"]))])
            if faltando:
                brolls.desenhar(plano, pc, log, so=faltando)
            if novo_plano and plano:
                pr.etapa(f"Revisando os B-rolls do corte {ct['n']}", base_pct + 10 / max(1, len(lista)))
                plano = brolls.revisar(words_yt, ct, plano, pc, log)
            cartoes, novos_cartoes = [], False
            if ler_config().get("cartoes_cortes", True):
                novos_cartoes = not os.path.exists(os.path.join(pc, "cartoes.json"))
                try:
                    cartoes = insercoes.planejar_corte(words_yt, ct, pasta, pc, log)
                except Exception as e:
                    log(f"Corte {ct['n']} vai sem cartões por enquanto ({e}).")
            if not os.path.exists(f_out) or novo_plano or faltando or novos_cartoes:
                pr.etapa(f"Montando o corte {ct['n']}", base_pct + 20 / max(1, len(lista)))
                compor.montar(os.path.join(pasta, "youtube.mp4"), words_yt, trechos, ct, plano, pc, f_out, log, cartoes=cartoes)
        pr.etapa("Pronto", 100)
        pr.set(pronto=True)
        if proj.get("exportar_para"):
            exportar(pasta, proj["exportar_para"], log)
    except Exception as e:
        pr.set(erro=str(e))
        pr.log("ERRO: " + str(e))
        pr.log(traceback.format_exc()[-1500:])
    finally:
        usar_versao(None)


def refazer_broll(pasta, n, k, pedido=""):
    pr = Progresso(pasta)
    try:
        pr.set(ocupado=f"Refazendo B-roll {k + 1} do corte {n}")
        words_yt = _j(os.path.join(pasta, "youtube_palavras.json"))
        ct = next(c for c in _j(os.path.join(pasta, "cortes.json")) if c["n"] == n)
        pc = os.path.join(pasta, f"corte_{n}")
        brolls.refazer(words_yt, ct, pc, k, pedido, pr.log)
        remontar(pasta, n, pr)
    except Exception as e:
        pr.log(f"ERRO ao refazer: {e}")
    finally:
        pr.set(ocupado=None)


def tirar_broll(pasta, n, k):
    pc = os.path.join(pasta, f"corte_{n}")
    plano = _j(os.path.join(pc, "brolls.json"))
    plano.pop(k)
    json.dump(plano, open(os.path.join(pc, "brolls.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    remontar(pasta, n)


def remontar(pasta, n, pr=None):
    pr = pr or Progresso(pasta)
    words_yt = _j(os.path.join(pasta, "youtube_palavras.json"))
    trechos = _j(os.path.join(pasta, "youtube_trechos.json"))
    ct = next(c for c in _j(os.path.join(pasta, "cortes.json")) if c["n"] == n)
    pc = os.path.join(pasta, f"corte_{n}")
    pr.log(f"Remontando o corte {n}")
    versao = len([f for f in os.listdir(pc) if f.startswith(f"corte_{n}")]) + 1
    saida = os.path.join(pc, f"corte_{n}.mp4" if versao == 1 else f"corte_{n}_v{versao}.mp4")
    f_cart = os.path.join(pc, "cartoes.json")
    compor.montar(os.path.join(pasta, "youtube.mp4"), words_yt, trechos, ct, _j(os.path.join(pc, "brolls.json")), pc, saida, pr.log,
                  cartoes=_j(f_cart) if os.path.exists(f_cart) else None)
    ct_all = _j(os.path.join(pasta, "cortes.json"))
    for c in ct_all:
        if c["n"] == n:
            c["arquivo_final"] = os.path.basename(saida)
    json.dump(ct_all, open(os.path.join(pasta, "cortes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    pr.log(f"Corte {n} pronto: {os.path.basename(saida)}")
    proj = _j(os.path.join(pasta, "projeto.json"))
    if proj.get("exportar_para"):
        exportar(pasta, proj["exportar_para"], pr.log)


def girar(pasta, graus):
    """Muda a rotação do vídeo e refaz o que depende da imagem (transcrição, cortes e ideias de B-roll ficam)."""
    pj = os.path.join(pasta, "projeto.json")
    proj = _j(pj)
    proj["girar"] = int(graus)
    json.dump(proj, open(pj, "w", encoding="utf-8"), ensure_ascii=False)
    for f in ("youtube.mp4", "youtube_com_imagens.mp4"):
        try:
            os.remove(os.path.join(pasta, f))
        except OSError:
            pass
    for d in os.listdir(pasta):
        if d.startswith("corte_") and os.path.isdir(os.path.join(pasta, d)):
            for f in os.listdir(os.path.join(pasta, d)):
                if f.startswith(d) and f.endswith(".mp4"):
                    try:
                        os.remove(os.path.join(pasta, d, f))
                    except OSError:
                        pass
    processar(pasta)


def _reajustar_tempos(pasta, antigas, novas, log=print):
    """Quando a versão do YouTube é refeita (ex.: outro ritmo de cortes ou vídeo girado), os tempos mudam.
    Reaproveita os cortes e B-rolls já escolhidos, levando cada tempo para a mesma palavra na versão nova."""
    if len(antigas) != len(novas) or not novas:
        log("A fala mudou; os cortes serão escolhidos de novo.")
        try:
            os.remove(os.path.join(pasta, "cortes.json"))
        except OSError:
            pass
        for d in os.listdir(pasta):
            if d.startswith("corte_") and os.path.isdir(os.path.join(pasta, d)):
                os.rename(os.path.join(pasta, d), os.path.join(pasta, "_antigo_" + d + time.strftime("_%H%M%S")))
        return
    inicios = [w["s"] for w in antigas]
    import bisect

    def mapa(t):
        i = max(0, bisect.bisect_right(inicios, t) - 1)
        return max(0.0, novas[i]["s"] + (t - antigas[i]["s"]))

    f_i = os.path.join(pasta, "insercoes.json")
    if os.path.exists(f_i):
        ins = _j(f_i)
        for x in ins:
            x["tempo"] = round(mapa(x["tempo"]), 2)
        json.dump(ins, open(f_i, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    try:
        os.remove(os.path.join(pasta, "youtube_com_imagens.mp4"))
    except OSError:
        pass
    f_c = os.path.join(pasta, "cortes.json")
    if not os.path.exists(f_c):
        return
    cortes = _j(f_c)
    for ct in cortes:
        s_ant = ct["s"]
        ct["s"], ct["e"] = round(mapa(ct["s"]), 2), round(mapa(ct["e"]), 2)
        pc = os.path.join(pasta, f"corte_{ct['n']}")
        f_b = os.path.join(pc, "brolls.json")
        if os.path.exists(f_b):
            plano = _j(f_b)
            for b in plano:
                b["inicio"] = round(max(2.5, mapa(s_ant + b["inicio"]) - ct["s"]), 2)
            json.dump(plano, open(f_b, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if os.path.isdir(pc):
            for f in os.listdir(pc):
                if f.startswith(f"corte_{ct['n']}") and f.endswith(".mp4"):
                    try:
                        os.remove(os.path.join(pc, f))
                    except OSError:
                        pass
        ct.pop("arquivo_final", None)
    json.dump(cortes, open(f_c, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log("Cortes e B-rolls reaproveitados com os novos tempos.")


def _limpo(txt, maximo=60):
    """Nome que funciona como pasta/arquivo no Windows e no Drive."""
    import re
    txt = re.sub(r'[\\/:*?"<>|]+', " ", str(txt or "")).strip()
    txt = re.sub(r"\s+", " ", txt).strip(" .")
    if len(txt) > maximo:
        txt = txt[:maximo].rsplit(" ", 1)[0]
    return txt or "video"


def _pasta_final(pasta, destino):
    """'prontos/2026-10-02 - Tema do vídeo' (tema = título do YouTube até o '?' ou ':'). Fica salvo no projeto."""
    pj = os.path.join(pasta, "projeto.json")
    proj = _j(pj)
    if proj.get("pasta_pronta"):
        return proj["pasta_pronta"]
    titulo = ""
    info = os.path.join(pasta, "youtube_info.txt")
    if os.path.exists(info):
        titulo = open(info, encoding="utf-8").read().strip().split("\n")[0]
    for sep in ("?", ":", " - ", "|"):
        if sep in titulo and len(titulo.split(sep)[0].strip()) >= 12:
            titulo = titulo.split(sep)[0]
            break
    final = os.path.join(os.path.dirname(destino.rstrip("\\/")), f"{time.strftime('%Y-%m-%d')} - {_limpo(titulo or proj.get('nome'))}")
    proj["pasta_pronta"] = final
    json.dump(proj, open(pj, "w", encoding="utf-8"), ensure_ascii=False)
    return final


def exportar(pasta, destino, log=print):
    """Copia os resultados para a pasta 'prontos' (ex.: Google Drive/OneDrive), organizados:
    prontos/<data> - <tema>/YouTube/...  e  prontos/<data> - <tema>/Cortes/Corte 1 - TÍTULO.mp4"""
    import shutil
    final = _pasta_final(pasta, destino)
    if _j(os.path.join(pasta, "projeto.json")).get("tipo") == "vertical":
        return _exportar_vertical(pasta, final, log)
    yt, cts = os.path.join(final, "YouTube"), os.path.join(final, "Cortes")
    os.makedirs(yt, exist_ok=True)
    for f, nome in (("youtube_com_imagens.mp4", "Vídeo com imagens.mp4"), ("youtube.mp4", "Vídeo sem imagens.mp4"),
                    ("youtube.srt", "Legenda.srt"), ("youtube_info.txt", "Título, descrição e capítulos.txt"),
                    ("capa_1.jpg", "Capa 1.jpg"), ("capa_2.jpg", "Capa 2.jpg"), ("capa_3.jpg", "Capa 3.jpg")):
        if os.path.exists(os.path.join(pasta, f)):
            shutil.copy2(os.path.join(pasta, f), os.path.join(yt, nome))
    textos = []
    f_c = os.path.join(pasta, "cortes.json")
    for ct in (_j(f_c) if os.path.exists(f_c) else []):
        pc = os.path.join(pasta, f"corte_{ct['n']}")
        arq = ct.get("arquivo_final", f"corte_{ct['n']}.mp4")
        if os.path.exists(os.path.join(pc, arq)):
            os.makedirs(cts, exist_ok=True)
            shutil.copy2(os.path.join(pc, arq), os.path.join(cts, f"Corte {ct['n']} - {_limpo(ct.get('titulo', ''), 50)}.mp4"))
        textos.append(f"CORTE {ct['n']} — {ct.get('titulo', '')}\n{ct.get('legenda_post', '')}\n")
    creditos = []
    for ct in (_j(f_c) if os.path.exists(f_c) else []):
        f_b = os.path.join(pasta, f"corte_{ct['n']}", "brolls.json")
        for b in (_j(f_b) if os.path.exists(f_b) else []):
            if b.get("credito") and b["credito"] not in creditos:
                creditos.append(b["credito"])
    f_yb = os.path.join(pasta, "youtube_brolls", "brolls.json")
    cred_yt = [b["credito"] for b in (_j(f_yb) if os.path.exists(f_yb) else []) if b.get("credito")]
    cred_yt = list(dict.fromkeys(cred_yt))
    f_info = os.path.join(yt, "Título, descrição e capítulos.txt")
    if cred_yt and os.path.exists(f_info):
        open(f_info, "a", encoding="utf-8").write("\n\nVídeos de apoio (Pexels / Pixabay):\n" + "\n".join(cred_yt) + "\n")
    if creditos:
        textos.append("Vídeos de apoio (Pexels / Pixabay):\n" + "\n".join(creditos) + "\n")
    if textos:
        os.makedirs(cts, exist_ok=True)
        open(os.path.join(cts, "Legendas dos posts.txt"), "w", encoding="utf-8").write("\n".join(textos))
    log(f"Resultados copiados para: {final}")


def _exportar_vertical(pasta, final, log=print):
    import shutil
    pv = os.path.join(final, "Vertical")
    os.makedirs(pv, exist_ok=True)
    textos, creditos = [], []
    f_c = os.path.join(pasta, "cortes.json")
    lista = _j(f_c) if os.path.exists(f_c) else []
    for ct in lista:
        pc = os.path.join(pasta, f"corte_{ct['n']}")
        arq = ct.get("arquivo_final", f"corte_{ct['n']}.mp4")
        nome = (f"Parte {ct['n']} de {len(lista)}.mp4" if len(lista) > 1 else "Vídeo vertical.mp4")
        if os.path.exists(os.path.join(pc, arq)):
            shutil.copy2(os.path.join(pc, arq), os.path.join(pv, nome))
        if ct.get("legenda_post"):
            textos.append(f"{nome[:-4].upper()}\n{ct['legenda_post']}\n")
        f_b = os.path.join(pc, "brolls.json")
        for b in (_j(f_b) if os.path.exists(f_b) else []):
            if b.get("credito") and b["credito"] not in creditos:
                creditos.append(b["credito"])
    if creditos:
        textos.append("Vídeos e fotos de apoio (Pexels / Pixabay / Wikimedia):\n" + "\n".join(creditos) + "\n")
    if textos:
        open(os.path.join(pv, "Legendas e créditos.txt"), "w", encoding="utf-8").write("\n".join(textos))
    log(f"Resultados copiados para: {final}")


def refazer_imagens(pasta):
    """Pede ao Gemini outras imagens para o vídeo do YouTube."""
    for f in ("insercoes.json", "youtube_com_imagens.mp4", os.path.join("youtube_brolls", "brolls.json")):
        try:
            os.remove(os.path.join(pasta, f))
        except OSError:
            pass
    processar(pasta)
