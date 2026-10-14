# Edição Cinematográfica com Remotion — integração isolada

## Objetivo
Botão no menu do Editor Natinha original que abre a página /remotion.
O modo antigo não foi modificado: app.py apenas registra um Blueprint; interface.html só recebeu um link.

## Pastas
- Módulo: integracoes/remotion/ (bridge.py, runner.py, painel.html)
- Motor pré-existente: ..\\NATINHA_CINEMATIC_EDITOR_V1\\robo\\robo.py (não modificado)
- Progresso e intermediários do motor: motor experimental/robo/jobs/rm_...
- Prévias e saídas separadas: editor_natinha/Resultados/Remotion/rm_...
- Backup verificável: editor_natinha/_backup_integracao_remotion_20261009_122632

## Como usar
1. Depois que o Editor Natinha for reiniciado com segurança, abra a página habitual.
2. Clique em "🎬 Edição Cinematográfica · Remotion" no menu.
3. Selecione um vídeo ou digite caminho completo; escolha formato e estilo.
4. Clique INICIAR EDIÇÃO. Acompanhe progresso real e logs.
5. Veja prévias, baixe MP4/legendas; clique ABRIR RESULTADOS para abrir no PC.
6. Se falhar, RETOMAR JOB aproveita checkpoints já existentes do motor.

## Recursos comprovados do motor experimental (até 09/10/2026)
- Cortes verticais 9:16 automáticos gerados e tecnicamente validados com dois trechos distintos.
- YouTube com B-roll horizontal em teste já registrado; aparência ainda depende de revisão.
- YouTube limpo é FFmpeg, não uma composição Remotion.
- Vertical limpo está DESABILITADO porque não há implementação estável separada.
- Sem caixa de autorização, consultas Gemini/Pixabay não são iniciadas pelo adaptador.
- Não copia chaves e nunca envia resultados ao Postador.

## Restrições
- Apenas uma renderização pesada do motor por vez.
- Modelos de transcrição trabalham localmente, sem IA externa no modo offline.
- São necessárias conferência humana de contexto, continuidade e estética.
- Não misturar as saídas com versões antigas ou pastas sincronizadas/monitoradas.

## Restauração
Use COMO_RESTAURAR.txt dentro do backup, fora do horário de edição.
Os arquivos antigos continuam na pasta projetos, sem migração.

## Testes
Compilação Python: OK; JS: OK; rotas Flask /, /remotion e /api/versoes: 200.
Testes reais e limitações devem ser registrados separadamente, não presumidos.
