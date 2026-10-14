# Correção de arquitetura da integração, 09/10/2026

## O erro
A primeira versão do menu chamava exclusivamente o robô cinematográfico experimental.
Isso não reutilizava transcrição, análise de cortes, limpeza e B-rolls do Editor Natinha original.
Os dois exemplos anteriores demonstravam o experimental isolado, não integração.

## Nova integração implementada (em validação)
- `legado_remotion.py`: transforma artefatos do Natinha original em plano para o compositor Remotion.
- `legado_api.py`: lista projetos originais e permite escolher um corte para remasterização.
- `bridge.py`: protege contra renderizações simultâneas, acrescenta rotas nativas e os registros ao painel.
- `painel.html`: identifica o modo experimental como separado e adiciona 'Natinha original + Remotion'.
- Fonte original sempre somente leitura. Saídas novas isoladas em Resultados/Remotion.

## Dados que realmente são reaproveitados
1. youtube.mp4: áudio e vídeo após limpeza do Natinha original
2. cortes.json: início/fim e seleção editorial já feita pelo Natinha original
3. youtube_palavras.json: tempos de fala do sistema original
4. corte_N/brolls.json + MP4s: seleção e recursos preparados pelo motor do Natinha original
5. Remotion renderiza por cima, usando composição, tipografia, posicionamento e movimento do JSX genérico existente

## Testes concretos
- Código Python compila e a UI JavaScript passa em node --check.
- /api/remotion/original/projetos retornou 24 projetos válidos.
- Caminho inválido bloqueado (HTTP 400).
- Nova renderização negada enquanto um render Remotion de outro processo estava ativo (HTTP 409).
- Para o projeto d6694ec8f675fe87d219143d42bc7bae_0210_1905 / corte 1:
  plano preparado para 18s usando 17 blocos de legenda temporizados pelo original,
  uma cena B-roll reaproveitada do original, com rastreabilidade gravada.
- O teste de MP4 combinado foi PAUSADO: surgiu outra renderização Remotion externa.
  Somente nosso subprocesso foi interrompido. Claude, Editor Natinha e render externo confirmados ativos depois.

## Pendências que NÃO devem ser apresentadas como concluídas
- Exportar e validar MP4 produzido por Natinha original + Remotion, do início ao fim.
- Processar um MP4 INÉDITO inteiramente pelo Natinha original e enviar automaticamente ao Remotion em um único clique.
- Acabamento e direção de arte: requer assistir vídeo e revisão da usuária.
- Ativação no servidor habitual da porta 7860: exige recarregar o processo Flask quando não houver edição ativa.
- Integração de versões V4 e outros motores legados: fora desta entrega até teste.
- Garantir retomada após travamento real, formato horizontal integrado, 1 a 3 cortes e progresso por etapa.

## Regra de preservação
Nenhum motor antigo foi modificado por esta correção. O botão experimental continua, explicitamente marcado como separado.
Não encerrar Claude/Editor/Postador/Commander, não publicar e não usar serviços pagos.
