import json
import crypto_engine

ID_UNIDADE = "ut-juliet"

def inicializar_unidade():
    print(f"🪖 Iniciando a fabricação de chaves para a {ID_UNIDADE}...")
    
    # 1. Fabricando as chaves usando nossa engine
    rsa_priv, rsa_pub = crypto_engine.gerar_chaves_rsa()
    ecdsa_priv, ecdsa_pub = crypto_engine.gerar_chaves_ecdsa()
    
    print("✅ Chaves RSA e ECDSA geradas matematicamente.")
    
    # 2. Convertendo para Base64 para podermos salvar em formato texto
    chaves_rsa = crypto_engine.exportar_chaves_base64(rsa_priv, rsa_pub)
    chaves_ecdsa = crypto_engine.exportar_chaves_base64(ecdsa_priv, ecdsa_pub)
    
    # 3. Montando o dicionário de configuração exigido pelo professor
    config = {
        "mqtt_broker": "broker.hivemq.com",
        "mqtt_port": 1883,
        "id_unidade": ID_UNIDADE,
        "arquivo_chaves": "chaves_confiadas.json",
        "minhas_chaves": {
            "rsa_publica": chaves_rsa["public_key"],
            "rsa_privada": chaves_rsa["private_key"],
            "ecdsa_publica": chaves_ecdsa["public_key"],
            "ecdsa_privada": chaves_ecdsa["private_key"]
        }
    }
    
    # 4. Salvando nosso cofre secreto
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
        
    # 5. Criando a lista de contatos (vazia por enquanto)
    with open("chaves_confiadas.json", "w", encoding="utf-8") as f:
        json.dump({}, f, indent=4)
        
    print("✅ Sucesso! Arquivos 'config.json' (SEU COFRE) e 'chaves_confiadas.json' (SEUS CONTATOS) foram criados.")
    print("A Fase 1 está concluída. A UT-Juliet agora tem identidade criptográfica!")

if __name__ == "__main__":
    inicializar_unidade()