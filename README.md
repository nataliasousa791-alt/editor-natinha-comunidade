# Editor Natinha Comunidade | MVP independente

**Demonstração funcional local. NÃO é o Editor Natinha de produção.**

Este repositório contém uma demonstração isolada de edição de vídeo com Python e FFmpeg. Não acessa Google Drive, não usa senhas, serviços externos ou o computador da autora.

## O que faz

- Abre MP4, MOV, MKV e M4V.
- Exporta vídeo master horizontal 1280 × 720 preservando a proporção.
- Gera três exemplos de cortes verticais 720 × 1280 com recorte central.
- Grava relatório JSON e verifica duração e resolução.

**Limitações:** não tem edição narrativa por IA, transcrição, legendas, Remotion, B-roll, remoção automática de silêncios nem publicação. Os cortes são temporais, não editoriais.

## Requisitos e execução

Instale Python 3.10+ e FFmpeg/FFprobe no PATH. No PowerShell, dentro da pasta do repositório:

    python .\editor.py --input "C:\Videos\meu_video.mp4" --output ".\saidas"

Para ver opções: `python .\editor.py --help`.

O vídeo de entrada nunca é sobrescrito. Os resultados são gravados numa pasta nova.

## Privacidade e segurança

Não adicione tokens, credenciais, arquivos `.env`, configurações do Google Drive, vídeos pessoais nem logs. Execute o verificador local `python tools/verificar_seguranca.py .` antes de mudanças.

**O código do Editor Natinha real não está aqui:** a máquina com o editor original estava desconectada e continua pendente de auditoria. A licença também não foi definida. Consulte os documentos em `docs/` antes de qualquer abertura ao público.
