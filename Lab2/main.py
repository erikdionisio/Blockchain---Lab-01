import json
import time
import paho.mqtt.client as mqtt
import crypto_engine

# ==========================================
# 1. CONFIGURAÇÕES E CARREGAMENTO DE CHAVES
# ==========================================
with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

MEU_ID = CONFIG["id_unidade"]
MINHAS_CHAVES = CONFIG["minhas_chaves"]

# Carregando as nossas chaves privadas na memória
rsa_priv_local = crypto_engine.load_rsa_priv_key(MINHAS_CHAVES["rsa_privada"])
ecdsa_priv_local = crypto_engine.load_ecdsa_priv_key(MINHAS_CHAVES["ecdsa_privada"])

def carregar_contatos():
    try:
        with open("chaves_confiadas.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def salvar_contatos(contatos):
    with open("chaves_confiadas.json", "w", encoding="utf-8") as f:
        json.dump(contatos, f, indent=4)

# Injetando o Oráculo diretamente na nossa agenda para garantirmos o teste
agenda = carregar_contatos()
agenda["oraculo"] = {
    "chave_publica_rsa": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0JYEsxupPYOio+u8xHdzSNLQgQoPwFx/qceHQJPy2KzNSCXz3FFyKkXaso4UTorzy8XXDv5WkRC1AlDDVu28ANXlrZqLyjLZ8DdplHig2KSxYV5MXA5TyqMDeCAW5CWi+na5Xwr9IbtuTfCv65YeB3QRgZWjZ4oVxpGVek+4dec0qChNl6pL9KmgI4u5CHHC8d7z6MovK0+eN0aMIT2bWgri29tT9sDCoHEGaab1576+SXK3iDXlLkeehJ/h72lqu3HmSL/B5ZE+pKLVLJogSwwMCTejrfTXf5acj9EOq83wGNLTjHIKr2iMz+SZzFS4vxk6qMgltCXjBZfXalzLnwIDAQAB",
    "chave_publica_ecdsa": "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEfmgdDET1IKOR2OxLI9KBBzFB97GyrJKipAuwSrMhDn1w93ieoCb7etbYX5/wrUic9xX5LQbUdgyKSRuCnTPAeQ=="
}
salvar_contatos(agenda)

# ==========================================
# 2. FLUXO DO MQTT (RÁDIO TÁTICO)
# ==========================================
def on_connect(client, userdata, flags, rc):
    print(f"📡 Conectado ao CCU (Broker HiveMQ) com status: {rc}")
    
    # 1. Nos inscrevemos na nossa própria caixa de entrada, nas chaves dos outros e no alarme de revogação
    client.subscribe(f"sisdef/direto/{MEU_ID}")
    client.subscribe("sisdef/broadcast/chaves/+")
    client.subscribe("sisdef/broadcast/revogacao")
    client.subscribe("sisdef/broadcast/notas")
    
    # 2. Publicamos quem nós somos para o mundo (Identidade)
    # A flag retain=True diz pro Broker segurar essa mensagem lá para sempre, para quem conectar depois ler
    payload_identidade = {
        "id_unidade": MEU_ID,
        "chave_publica_rsa": MINHAS_CHAVES["rsa_publica"],
        "chave_publica_ecdsa": MINHAS_CHAVES["ecdsa_publica"]
    }
    client.publish(f"sisdef/broadcast/chaves/{MEU_ID}", json.dumps(payload_identidade), retain=True)
    print(f"📣 Nossa Identidade ({MEU_ID}) foi transmitida no CCU.")

def on_message(client, userdata, msg):
    topico = msg.topic
    payload_texto = msg.payload.decode('utf-8')
    
    # CENÁRIO 1: Ouvimos alguém gritando as próprias chaves no rádio
    if topico.startswith("sisdef/broadcast/chaves/"):
        if MEU_ID in topico: return # Ignora nós mesmos
        
        try:
            dados = json.loads(payload_texto)
            id_aliado = dados.get("id_unidade")
            if id_aliado:
                id_aliado = id_aliado.lower()
                contatos = carregar_contatos()
                contatos[id_aliado] = {
                    "chave_publica_rsa": dados.get("chave_publica_rsa"),
                    "chave_publica_ecdsa": dados.get("chave_publica_eddsa", dados.get("chave_publica_ecdsa"))
                }
                salvar_contatos(contatos)
                print(f"\n🤝 Novas chaves armazenadas com sucesso: {id_aliado}")
        except:
            pass 
            
    # CENÁRIO 2: Uma mensagem direta secreta para a UT-Juliet!
    elif topico == f"sisdef/direto/{MEU_ID}":
        print("\n" + "🔥"*20)
        print("🚨 ALERTA: MENSAGEM DIRETA RECEBIDA 🚨")
        try:
            pacote = json.loads(payload_texto)
            remetente_id = pacote.get("id_unidade", "oraculo") 
            
            contatos = carregar_contatos()
            if remetente_id not in contatos:
                print(f"❌ Abortar: {remetente_id} não está na nossa agenda de chaves confiáveis.")
                return
                
            ecdsa_pub_remetente = crypto_engine.load_ecdsa_pub_key(contatos[remetente_id]["chave_publica_ecdsa"])
            texto_limpo = crypto_engine.decifrar_e_validar(pacote, rsa_priv_local, ecdsa_pub_remetente)
            print(f"✅ VERIFICADO DE: {remetente_id}")
            print(f"📝 CONTEÚDO DECIFRADO: {texto_limpo}")
            
        except Exception as e:
            print(f"❌ INTRUSÃO DETECTADA: {e}")
        print("🔥"*20 + "\n> ", end="")

    # CENÁRIO 3: 🚨 Alarme de Revogação
    elif topico == "sisdef/broadcast/revogacao":
        try:
            pacote = json.loads(payload_texto)
            remetente_id = pacote.get("remetente")
            dados_revogacao = pacote.get("revogacao")
            assinatura_b64 = pacote.get("assinatura_b64")
            
            contatos = carregar_contatos()
            if remetente_id not in contatos: return
                
            texto_revogacao = json.dumps(dados_revogacao, separators=(',', ':'))
            ecdsa_pub_remetente = crypto_engine.load_ecdsa_pub_key(contatos[remetente_id]["chave_publica_ecdsa"])
            
            if crypto_engine.validar_assinatura(texto_revogacao, assinatura_b64, ecdsa_pub_remetente):
                unidade_alvo = dados_revogacao.get("unidade_revogada").lower()
                if unidade_alvo in contatos:
                    del contatos[unidade_alvo]
                    salvar_contatos(contatos)
                    print(f"\n🚨 ACESSO REVOGADO: A unidade '{unidade_alvo}' foi expulsa da nossa agenda por ordem de {remetente_id}!")
            else:
                print(f"\n❌ ALARME FALSO: Assinatura inválida detectada de {remetente_id}.")
        except Exception as e:
            print(f"Erro ao processar revogação: {e}")

    # CENÁRIO 4: 🏆 Placar de Notas
    elif topico == "sisdef/broadcast/notas":
        try:
            placar = json.loads(payload_texto)
            # 🛡️ BLINDAGEM: Se a mensagem for só o comando de alguém pedindo notas, ignoramos.
              
            print("\n" + "🏆"*10)
            print("PLACAR DE NOTAS ATUALIZADO:")
            print(json.dumps(placar, indent=4, ensure_ascii=False))
            print("🏆"*10 + "\n> ", end="")
        except:
            pass # Ignora mensagens mal formatadas

# ==========================================
# 3. INTERFACE DE COMANDO
# ==========================================
# Usamos int(time.time()) para gerar um ID de client único no Broker
client = mqtt.Client(client_id=f"cli_{MEU_ID}_{int(time.time())}")
client.on_connect = on_connect
client.on_message = on_message

def enviar_ordem_taticamente(destino_id, mensagem, cmd_opcional=None):
    contatos = carregar_contatos()
    if destino_id not in contatos:
        print("❌ Destino não encontrado. Aguarde eles publicarem as chaves no CCU.")
        return
        
    print("🔒 Cifrando mensagem...")
    rsa_pub_dest = crypto_engine.load_rsa_pub_key(contatos[destino_id]["chave_publica_rsa"])
    
    pacote_seguro = crypto_engine.cifrar_e_assinar(mensagem, rsa_pub_dest, ecdsa_priv_local)
    pacote_seguro["id_unidade"] = MEU_ID
    
    # Injeta o comando na raiz se ele existir
    if cmd_opcional:
        pacote_seguro["cmd"] = cmd_opcional
    
    topico_destino = f"sisdef/direto/{destino_id}"
    client.publish(topico_destino, json.dumps(pacote_seguro))
    print(f"🚀 Pacote cifrado enviado para {topico_destino}!")

def enviar_ordem_revogacao(unidade_alvo):
    from datetime import datetime, timezone
    
    # 1. Monta o pacote interno
    payload_revogacao = {
        "unidade_revogada": unidade_alvo.lower(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # 2. Assina o pacote (compactado para não ter problema de espaços)
    texto_revogacao = json.dumps(payload_revogacao, separators=(',', ':'))
    assinatura_b64 = crypto_engine.assinar_texto(texto_revogacao, ecdsa_priv_local)
    
    # 3. Monta o payload final
    pacote_final = {
        "remetente": MEU_ID,
        "revogacao": payload_revogacao,
        "assinatura_b64": assinatura_b64
    }
    
    client.publish("sisdef/broadcast/revogacao", json.dumps(pacote_final))
    print(f"🚀 Alarme de revogação contra '{unidade_alvo}' disparado no CCU!")

def enviar_resposta_oraculo(resposta_matematica):
    contatos = carregar_contatos()
    if "oraculo" not in contatos:
        return
        
    print("🔒 Cifrando resposta do desafio...")
    rsa_pub_dest = crypto_engine.load_rsa_pub_key(contatos["oraculo"]["chave_publica_rsa"])
    
    # Cifra estritamente a string da resposta (ex: "12"), sem JSON.
    pacote_seguro = crypto_engine.cifrar_e_assinar(resposta_matematica, rsa_pub_dest, ecdsa_priv_local)
    pacote_seguro["id_unidade"] = MEU_ID
    pacote_seguro["cmd"] = "resposta" 
    
    client.publish("sisdef/direto/oraculo", json.dumps(pacote_seguro))
    print("🚀 Resposta enviada para o Oráculo!")

def solicitar_placar():
    # Envia o comando para o broadcast de notas
    payload = {"cmd": "atualizar_notas"}
    client.publish("sisdef/broadcast/notas", json.dumps(payload))
    print("📊 Solicitando notas... Fique de olho no rádio.")

def menu_interativo():
    print("Iniciando conexões de rádio...")
    client.connect(CONFIG["mqtt_broker"], CONFIG["mqtt_port"], 60)
    client.loop_start()
    time.sleep(2)
    
    while True:
        print("\n--- COMANDO TÁTICO: UT-JULIET ---")
        print("1. Solicitar Desafio Matemático ao Oráculo")
        print("2. Enviar Resposta do Desafio")
        print("3. Consultar Placar de Notas")
        print("4. Testar conexão com Oráculo (Echo)")
        print("5. Enviar ordem secreta para outra Unidade")
        print("6. Emitir Alarme de Revogação")
        print("0. Sair e Desconectar")
        op = input("> ")
        
        if op == "1":
            # Passo 1: O Oráculo exige o gatilho em texto plano
            payload_desafio = json.dumps({"id_unidade": MEU_ID, "cmd": "desafio"})
            client.publish("sisdef/direto/oraculo", payload_desafio)
            print("⏳ Solicitando desafio... Aguarde a transmissão criptografada do Oráculo!")
            
        elif op == "2":
            # Passo 3: A resposta vai pesadamente cifrada
            resp = input("Digite APENAS o número da resposta: ")
            enviar_resposta_oraculo(resp)
            
        elif op == "3":
            solicitar_placar()
            
        elif op == "4":
            # Echo: Gatilho em texto plano
            payload_echo = json.dumps({"id_unidade": MEU_ID, "cmd": "echo"})
            client.publish("sisdef/direto/oraculo", payload_echo)
            print("⏳ Solicitando teste de Echo ao Oráculo...")
            
        elif op == "5":
            # Comunicação lateral com aliados
            dest = input("ID do Destino (ex: ut-alfa): ").lower()
            msg = input("Digite a Ordem (texto puro): ")
            enviar_ordem_taticamente(dest, msg)
            
        elif op == "6":
            alvo = input("ID da Unidade Traidora (ex: ut-bravo): ").lower()
            enviar_ordem_revogacao(alvo)
            
        elif op == "0":
            client.loop_stop()
            client.disconnect()
            print("🪖 Desconectado.")
            break

if __name__ == "__main__":
    menu_interativo()