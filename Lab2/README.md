### 🔴 FASE 1: Geração de Identidade e Logística de Chaves (IFF)
* **Meta:** Estabelecer a infraestrutura básica de chaves locais e gerenciamento de arquivos.
* **Tarefas:**
  1. Implementar rotinas usando a biblioteca `cryptography` para gerar chaves RSA (2048 bits) e ECDSA (`secp256r1`).
  2. Criar funções de serialização/exportação das chaves públicas no formato binário DER e posterior conversão para string Base64.
  3. Implementar a persistência local: carregar e salvar chaves confiadas no arquivo local `chaves_confiadas.json` e as próprias chaves privadas no arquivo seguro de configuração `config.json`.

### 🟡 FASE 2: Desenvolvimento da Crypto Engine Híbrida
* **Meta:** Construir as funções puras de cifragem e decifragem isoladas de rede.
* **Tarefas:**
  1. **Função Cifrar/Assinar:** Receber payload original, calcular hash SHA-256, assinar com a chave privada ECDSA local. Gerar chave AES-256 aleatória, cifrar payload com modo GCM, cifrar a chave AES com a chave pública RSA do destinatário. Empacotar tudo em strings Base64 organizadas em um dicionário JSON.
  2. **Função Decifrar/Validar:** Executar o fluxo reverso exato. Decifrar a chave AES usando a RSA privada local, abrir o payload AES-GCM validando a integridade da tag, calcular o hash do texto limpo e validar a assinatura digital ECDSA usando a chave pública do remetente obtida do arquivo de contatos.

### 🟢 FASE 3: Integração com Transporte MQTT e Teste com o Oráculo
* **Meta:** Conectar a Crypto Engine à rede em tempo real usando a biblioteca `paho-mqtt`.
* **Tarefas:**
  1. Configurar os callbacks `on_connect` (para assinar os tópicos `sisdef/direto/ut-grupo03`, `sisdef/broadcast/chaves/+` e `sisdef/broadcast/revogacao`) e `on_message`.
  2. Implementar a rotina automática de IFF: ao conectar, publicar o JSON de chaves públicas locais no tópico de broadcast correspondente com `retain=True`.
  3. **Teste de Fogo (O Oráculo):** Publicar as chaves públicas da nossa UT, carregar as chaves públicas fornecidas pelo Oráculo no documento de laboratório, enviar o comando estruturado `{"id_unidade": "ut-grupo03", "cmd": "echo"}` criptografado para o tópico `sisdef/direto/oraculo`, capturar a resposta na nossa caixa de entrada e decifrá-la com sucesso.

### 🔵 FASE 4: Protocolo de Emergência e Revogação Dinâmica
* **Meta:** Tornar a rede resiliente contra nós capturados ou traidores.
* **Tarefas:**
  1. Implementar a rotina de leitura do tópico `sisdef/broadcast/revogacao`.
  2. Ao receber um JSON de revogação, validar a assinatura do remetente que emitiu o alerta para garantir que a ordem de revogação não foi forjada pelo próprio "Sombra".
  3. Se a assinatura for legítima, remover permanentemente os registros da unidade comprometida do arquivo `chaves_confiadas.json`, cortar qualquer envio de mensagens para ela e descartar sumariamente qualquer pacote recebido que contenha o identificador dela, registrando o incidente em um log de segurança persistente.

---

## 6. Arquitetura Sugerida de Arquivos do Sistema

Para manter a modularidade e garantir a corretude exigida na operação, o repositório do Jupyter Notebook / Script Python será organizado na seguinte estrutura lógica de dependências:

├── config.json               # Configurações do Broker e chaves privadas locais da UT
├── chaves_confiadas.json     # Banco de dados local de chaves públicas descobertas na rede
├── crypto_engine.py          # Funções puras de criptografia simétrica, assimétrica e assinaturas
├── mqtt_manager.py           # Gerenciamento de conexões, publicações e inscrições em tópicos
└── main.py / notebook.ipynb  # Loop principal do painel tático de comando e controle

