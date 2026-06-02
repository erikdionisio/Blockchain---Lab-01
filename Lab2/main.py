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
    
    # 2. Publicamos quem nós somos para o mundo (Identidade)
    # A flag retain=True diz pro Broker segurar essa mensagem lá para sempre, para quem conectar depois ler
    payload_identidade = {
        "id_unidade": MEU_ID,
        "chave_publica_rsa": MINHAS_CHAVES["rsa_publica"],
        "chave_publica_eddsa": MINHAS_CHAVES["ecdsa_publica"]
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
                contatos = carregar_contatos()
                # A chave ecdsa pode vir nomeada como eddsa (conforme documento), garantimos os dois
                contatos[id_aliado] = {
                    "chave_publica_rsa": dados.get("chave_publica_rsa"),
                    "chave_publica_ecdsa": dados.get("chave_publica_eddsa", dados.get("chave_publica_ecdsa"))
                }
                salvar_contatos(contatos)
                print(f"\n🤝 Novas chaves armazenadas com sucesso: {id_aliado}")
        except:
            pass # Lixo na rede, ignora
            
    # CENÁRIO 2: Uma mensagem direta secreta para a UT-Juliet!
    elif topico == f"sisdef/direto/{MEU_ID}":
        print("\n" + "🔥"*20)
        print("🚨 ALERTA: MENSAGEM DIRETA RECEBIDA 🚨")
        try:
            pacote = json.loads(payload_texto)
            remetente_id = pacote.get("id_unidade", "oraculo") # Se vier sem id, assumimos que foi o bot
            
            contatos = carregar_contatos()
            if remetente_id not in contatos:
                print(f"❌ Abortar: {remetente_id} não está na nossa agenda de chaves confiáveis.")
                return
                
            # Carrega a pública do remetente
            ecdsa_pub_remetente = crypto_engine.load_ecdsa_pub_key(contatos[remetente_id]["chave_publica_ecdsa"])
            
            # MAGIA: Tenta abrir o cofre. Se for do Sombra, a função explode e dá ValueError
            texto_limpo = crypto_engine.decifrar_e_validar(pacote, rsa_priv_local, ecdsa_pub_remetente)
            print(f"✅ VERIFICADO DE: {remetente_id}")
            print(f"📝 CONTEÚDO DECIFRADO: {texto_limpo}")
            
        except Exception as e:
            print(f"❌ INTRUSÃO DETECTADA: {e}")
        print("🔥"*20 + "\n> ", end="")


# ==========================================
# 3. INTERFACE DE COMANDO
# ==========================================
# Usamos int(time.time()) para gerar um ID de client único no Broker
client = mqtt.Client(client_id=f"cli_{MEU_ID}_{int(time.time())}")
client.on_connect = on_connect
client.on_message = on_message

def enviar_ordem_taticamente(destino_id, mensagem):
    contatos = carregar_contatos()
    if destino_id not in contatos:
        print("❌ Destino não encontrado. Aguarde eles publicarem as chaves no CCU.")
        return
        
    print("🔒 Cifrando mensagem...")
    rsa_pub_dest = crypto_engine.load_rsa_pub_key(contatos[destino_id]["chave_publica_rsa"])
    
    # Chama o nosso motor da Fase 2!
    pacote_seguro = crypto_engine.cifrar_e_assinar(mensagem, rsa_pub_dest, ecdsa_priv_local)
    pacote_seguro["id_unidade"] = MEU_ID
    
    topico_destino = f"sisdef/direto/{destino_id}"
    client.publish(topico_destino, json.dumps(pacote_seguro))
    print(f"🚀 Pacote cifrado enviado para {topico_destino}!")


def menu_interativo():
    print("Iniciando conexões de rádio...")
    client.connect(CONFIG["mqtt_broker"], CONFIG["mqtt_port"], 60)
    # Roda o MQTT em background
    client.loop_start()
    
    # Dá uns segundinhos pro HiveMQ conectar
    time.sleep(2)
    
    while True:
        print("\n--- COMANDO TÁTICO: UT-JULIET ---")
        print("1. Desafiar o Oráculo (O Teste dos 30%)")
        print("2. Enviar ordem secreta para outra Unidade")
        print("0. Sair e Desconectar")
        op = input("> ")
        
        if op == "1":
            # O professor pediu pra mandar um JSON específico pro Oraculo em formato string
            payload_oraculo = json.dumps({"id_unidade": MEU_ID, "cmd": "echo"})
            enviar_ordem_taticamente("oraculo", payload_oraculo)
            print("⏳ Mensagem enviada... Aguardando resposta criptografada do Oráculo...")
            time.sleep(3) # Pausa dramática esperando a rede
            
        elif op == "2":
            dest = input("ID do Destino (ex: ut-alfa): ").lower()
            msg = input("Digite a Ordem (texto puro): ")
            enviar_ordem_taticamente(dest, msg)
            
        elif op == "0":
            client.loop_stop()
            client.disconnect()
            print("🪖 Desconectado. Sistema encerrado.")
            break

if __name__ == "__main__":
    menu_interativo()