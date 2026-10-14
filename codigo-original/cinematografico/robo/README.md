# Robô Editor Natinha (Remotion)

Vídeo bruto -> corte(s) verticais 9:16 editados com Remotion, salvos para APROVAÇÃO (nada é publicado).

## Como usar
- Duplo clique em `ROBO_EDITOR_NATINHA.bat` (na pasta do projeto) -> escolha o vídeo -> informe início/fim (opcional) e nº de cortes.
- Ou pelo terminal, dentro de `robo\`:
  `python robo.py "C:\caminho\video.mp4" --inicio 190 --fim 290 --cortes 1`
  Opções: `--alvo 45` (duração alvo em s), `--nome NOME`, `--sem-ia` (só regras, sem Gemini).
- Saída: `robo\jobs\<nome>\corte1\<nome>_corte1_PREVIA.mp4` + `plano.json`, `mapa.json`, `qa.json`, `STATUS.txt`, `robo.log`.
- Se cair no meio, rode de novo o mesmo comando: etapas prontas (sondagem, transcrição, cortes, montagem) são reaproveitadas.

## O que o robô faz sozinho
1. **Sondagem** (`nucleo/sondar.py`): FFprobe (SAR/DAR/rotação) + detector de rosto em 4 rotações -> orientação real e posição/tamanho do rosto.
2. **Normalização** (`nucleo/montar.py`): gira, pixels quadrados, 30 fps CFR, leve limpeza; nunca altera o original.
3. **Transcrição** (`nucleo/transcrever.py`, cópia do editor principal): faster-whisper com tempo por palavra.
4. **Corte narrativo** (`nucleo/cortes.py`): IA Gemini (grátis; chave lida só-leitura do config antigo) escolhe gancho->argumento->fechamento; validado por regras, com fallback 100% por regras. Gera o MAPA bruto->timeline cortando só no silêncio.
5. **Montagem** A-roll + voz (FFmpeg, fades de 6 ms, loudnorm -14 LUFS).
6. **Plano de cenas** (`nucleo/planejar.py`): abertura (título literal), B-roll real por conceito, cartões tipográficos, números falados, fechamento palavra a palavra, legendas com destaque. Todo texto na tela é trecho literal da fala.
7. **B-roll** (`nucleo/biblioteca.py`): biblioteca local + busca Pixabay por conceito (`config_robo.json`), filtra 3D/ilustração, nunca repete clipe no mesmo vídeo (`biblioteca/usados.json`). Sem clipe pertinente -> Natinha fica em cena.
8. **Render** Remotion genérico (`remotion/src/robo/Robo.jsx`) via `--props=plano.json` + `--public-dir` do job.
9. **QA** (`nucleo/qa.py`): 1080x1920, duração, áudio, telas pretas, congelamento, retranscrição para medir sync das legendas, repetição de assets.

## Ajustes sem mexer em código
`config_robo.json`: duração mín/alvo/máx, pausa máxima, conceitos (gatilhos e buscas de B-roll), palavras sensíveis sem imagem, termos proibidos na busca.

## Limites atuais (MVP)
- Pertinência fina dos B-rolls baixados automaticamente (`revisado: false` no manifest) e estética exigem revisão humana.
- Cortes de 60–150 s e 3 cortes por vídeo: suportado por parâmetro (`--alvo`, `--cortes`), ainda não validado em produção.
- Sem interface gráfica própria além do BAT.
