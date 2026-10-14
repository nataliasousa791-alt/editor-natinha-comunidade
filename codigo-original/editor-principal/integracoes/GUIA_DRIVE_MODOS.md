# Editor Natinha — integração automática com Google Drive (09/10/2026)

## Como usar depois da ativação
1. Abra o Editor Natinha habitual em http://localhost:7860 no PC que executa o editor.
2. Escolha uma das quatro opções: Vídeo completo + cortes, Cortes cinematográficos, YouTube cinematográfico ou Pacote cinematográfico completo.
3. Ajuste cortes/duração e autorize buscas online apenas se desejar.
4. No quadro **Vídeos enviados pelo Drive**, clique **Usar a opção selecionada no Drive**.
5. Confira o texto **Ativo para novos vídeos:** com a opção escolhida.
6. No celular, Google Drive > Editor Natinha > entrada > enviar MP4 (ou MOV/MKV).
7. O PC importará o vídeo quando estiver totalmente sincronizado e houver motor livre. Os resultados finalizados vão para Google Drive > Editor Natinha > prontos.

### Regras
- O modo salvo é usado apenas para novos vídeos da pasta `entrada`. Apenas clicar no cartão não altera a automação; é necessário salvar explicitamente. O padrão anterior V2 permanece até essa confirmação.
- `entrada_vertical` mantém o processamento vertical clássico separado.
- Os processos não são executados simultaneamente pelo monitor do Drive. Se outro Remotion ou editor clássico estiver ocupado, o arquivo espera em `entrada`.
- O arquivo bruto é preservado em `Resultados/Remotion/<job>/entrada/original.*` ou no projeto clássico.
- Produtos Remotion só aparecem em `prontos` após completar o processamento. São cópias para **revisão**, sem publicação.
- Remotion usa IA e busca de vídeos na internet apenas se o usuário habilitar a opção.
- Remotion com pacote exige pelo menos 6 GB livres antes de admitir o trabalho (mais espaço pode ser necessário para vídeos grandes).
- Se houver erro, o projeto e original ficam preservados. O histórico mostra o erro para corrigir e retomar; o monitor não entra em loop de falhas.
- O Drive sincroniza via rclone aproximadamente de minuto em minuto, enquanto o monitor local olha a pasta a cada 20 segundos.

### Backup e rollback
Backup integral dos arquivos centrais e config: `_backup_drive_modos_20261009_150709` com SHA256.
O código do módulo novo fica em `integracoes/drive_automacao.py`.
Outros arquivos aditivos: `app.py`, `nucleo/util.py`, `integracoes/remotion/bridge.py`, `static/natinha_unificado.js`, `static/natinha_unificado.css`, `interface.html`.
O `config.json` ainda não foi modificado por esta implantação: o modo efetivo continua clássico V2.
Para rollback, restaurar arquivos existentes da pasta de backup COM O EDITOR PARADO e remover apenas o registro do blueprint e os links do módulo novo; não apague `projetos`, `Resultados`, `nuvem_drive` ou os originais.

### Validações já realizadas
- Compilação Python e checagem JavaScript: aprovadas.
- Teste Flask de escolha do modo sem gravar a configuração real: aprovado.
- Simulação com vídeo fictício da pasta entrada: aceita job Remotion, bruto preservado e execução sem precisar de motor de vídeo no teste.
- Simulação de devolução de 1 YouTube + 3 cortes em `prontos`, com manifesto e sem publicar arquivos parciais: aprovada.
- Simulação do envio V2 legado: aprovada.
- Interface desktop 1280 px e celular 390 px: validada no servidor isolado 7871.
- Nenhum processamento pesado, API paga ou publicação foi iniciado por esses testes.

### Ativação pendente
A sessão principal na porta 7860 ainda estava executando a edição `rm_20261009_145220_68fafe` em 09/10/2026, logo não foi reiniciada para preservar o vídeo.
Assim que TODOS os processos Remotion/runner.py desse job terminarem, reiniciar somente a instância do Editor Natinha pelo iniciador editor_sempre.bat, sem encerrar Claude, Desktop Commander ou Postador.
Testar GET `http://127.0.0.1:7860/api/drive/modo` e GET `http://127.0.0.1:7860/api/remotion/capacidades` (ambos HTTP 200).
A integração de quatro vídeos em um job foi testada contratualmente, mas a produção real do pacote completo via Drive ainda requer teste ponta a ponta e revisão estética da usuária.
