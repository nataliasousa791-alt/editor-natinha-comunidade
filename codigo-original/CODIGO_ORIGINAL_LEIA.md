# Editor Natinha: codigo real compartilhado, copia higienizada

Esta pasta inclui o codigo-fonte dos dois modulos reais recuperados do computador da autora em 14/10/2026:

- editor-principal: painel Flask, motor Python, transcricao, cortes, YouTube, B-roll, integracao Remotion.
- cinematografico: robo de cortes narrativos, sondagem, voz, B-roll e composicoes React/Remotion.

A copia e independente do editor original. Nenhum processo, codigo ou video da instalacao original foi alterado.

## Como adaptar a sua maquina

Esta e a origem do projeto, NAO um instalador universal. Foi criado originalmente para Windows com caminhos locais. Sera necessario fazer adaptacoes e configurar dependencias.

1. Instale Python, FFmpeg/FFprobe no PATH e Node.js/npm.
2. No editor-principal, crie ambiente virtual e instale requirements.txt.
3. Copie config.example.json para config.json, preenchendo apenas SUAS PROPRIAS chaves.
4. No modulo cinematografico, use config_robo.example.json como modelo; algumas integracoes leem config do editor principal e precisam de caminhos locais.
5. Na pasta cinematografico/remotion, execute npm install.
6. Execute testes sem contas externas nem pastas de producao antes de usar arquivos reais.

Componentes que dependem de midias de terceiros, modelos locais, B-roll e fontes podem exigir instalacao propria ou ajustes. Os scripts usam bibliotecas especificas e nao foram testados de ponta a ponta fora do computador original.

## Credenciais e privacidade

Nao foram incluidas configuracoes reais, credenciais de IA, tokens Google Drive, rclone, arquivos pessoais, videos, logs, jobs, fontes nem ambientes virtuais. A auditoria automatica de segredos e heuristica e nao garante seguranca completa.

## Direitos

Licenca publica de codigo ainda nao definida. Divulgacao do codigo nao autoriza automaticamente redistribuicao comercial. Respeite licencas de bibliotecas e midias de terceiros.
