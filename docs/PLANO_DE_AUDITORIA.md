# Auditoria obrigatória antes da abertura ao público

Este repositório contém um MVP independente, não uma cópia do editor de produção.

- Identificar as pastas reais do Editor Natinha, incluindo scripts Python, FFmpeg, Remotion e automações.
- Fazer backup antes de alterar arquivos do editor original.
- Examinar arquivos e histórico Git com ferramenta especializada em segredos (por exemplo, Gitleaks).
- Remover ou substituir configurações pessoais, OAuth, rclone, cookies, chaves de API, senhas, caminhos de usuário, IPs e URLs de controle remoto.
- Revogar e substituir qualquer credencial que já tenha sido publicada.
- Verificar que mídias pessoais, transcrições, logs, bancos de dados e dados de jobs não entram no repositório.
- Auditar comandos externos, endpoints, downloads, publicação e exclusões.
- Testar instalação e execução em máquina limpa e isolada.
- Verificar direitos e licenças de bibliotecas, fontes e mídias.
- Escolher licença e aprovar divulgação, mantendo o repositório privado até lá.

A varredura heurística deste pacote não substitui revisão manual nem análise do histórico.
