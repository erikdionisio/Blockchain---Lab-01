import base64
from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.hazmat.primitives import serialization
import os
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ==========================================
# 1. GERAÇÃO DE CHAVES
# ==========================================
def gerar_chaves_rsa():
    """Gera o par de chaves RSA de 2048 bits para Confidencialidade."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    return private_key, private_key.public_key()

def gerar_chaves_ecdsa():
    """Gera o par de chaves ECDSA (secp256r1) para Assinatura/Autenticidade."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    return private_key, private_key.public_key()

# ==========================================
# 2. EXPORTAÇÃO E IMPORTAÇÃO (BASE64 <-> OBJETO)
# ==========================================
def exportar_chaves_base64(private_key, public_key):
    """Converte as chaves brutas em strings Base64 no padrão DER/PKCS8."""
    _priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    _pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    return {
        "private_key": base64.b64encode(_priv_bytes).decode('utf-8'),
        "public_key": base64.b64encode(_pub_bytes).decode('utf-8')
    }

def load_rsa_pub_key(b64_str):
    """Converte Base64 de volta para Objeto de Chave Pública RSA."""
    key_bytes = base64.b64decode(b64_str)
    return serialization.load_der_public_key(key_bytes)

def load_ecdsa_pub_key(b64_str):
    """Converte Base64 de volta para Objeto de Chave Pública ECDSA."""
    key_bytes = base64.b64decode(b64_str)
    return serialization.load_der_public_key(key_bytes)

# Funções extras vitais para carregar nossas próprias chaves privadas depois
def load_rsa_priv_key(b64_str):
    key_bytes = base64.b64decode(b64_str)
    return serialization.load_der_private_key(key_bytes, password=None)

def load_ecdsa_priv_key(b64_str):
    key_bytes = base64.b64decode(b64_str)
    return serialization.load_der_private_key(key_bytes, password=None)

# ==========================================
# 3. MOTOR DE CIFRAGEM (ENVIAR MENSAGEM)
# ==========================================
def cifrar_e_assinar(mensagem_str, rsa_pub_destinatario, ecdsa_priv_remetente):
    """
    Empacota uma mensagem aplicando Criptografia Híbrida e Assinatura Digital.
    """
    msg_bytes = mensagem_str.encode('utf-8')

    # 1. Assinatura Digital (Autenticidade e Não-Repúdio)
    # A biblioteca já calcula o hash SHA-256 e assina com a privada ECDSA
    assinatura = ecdsa_priv_remetente.sign(
        msg_bytes,
        ec.ECDSA(hashes.SHA256())
    )

    # 2. Criptografia Simétrica com AES-256-GCM (Confidencialidade e Integridade)
    chave_aes = AESGCM.generate_key(bit_length=256)
    aesgcm = AESGCM(chave_aes)
    nonce = os.urandom(12) # Vetor de inicialização recomendado de 96 bits
    
    # O AESGCM no Python retorna o ciphertext concatenado com a tag de 16 bytes no final
    ct_and_tag = aesgcm.encrypt(nonce, msg_bytes, associated_data=None)
    ciphertext = ct_and_tag[:-16] # Pega tudo, menos os últimos 16 bytes
    tag = ct_and_tag[-16:]        # Pega exatamente os últimos 16 bytes

    # 3. Envelopamento RSA (Cifrar a chave AES para compartilhamento seguro)
    chave_sessao_cifrada = rsa_pub_destinatario.encrypt(
        chave_aes,
        rsa_padding.OAEP(
            mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    # 4. Formatação Final para MQTT (Base64)
    return {
        "ciphertext_b64": base64.b64encode(ciphertext).decode('utf-8'),
        "tag_autenticacao_b64": base64.b64encode(tag).decode('utf-8'),
        "nonce_b64": base64.b64encode(nonce).decode('utf-8'),
        "chave_sessao_cifrada_b64": base64.b64encode(chave_sessao_cifrada).decode('utf-8'),
        "assinatura_b64": base64.b64encode(assinatura).decode('utf-8')
    }

# ==========================================
# 4. MOTOR DE DECIFRAGEM (RECEBER MENSAGEM)
# ==========================================
def decifrar_e_validar(pacote, rsa_priv_receptor, ecdsa_pub_remetente):
    """
    Desempacota uma mensagem garantindo todos os 5 pilares de segurança antes de ler.
    """
    # 1. Desfazer o Base64
    ciphertext = base64.b64decode(pacote["ciphertext_b64"])
    tag = base64.b64decode(pacote["tag_autenticacao_b64"])
    nonce = base64.b64decode(pacote["nonce_b64"])
    chave_sessao_cifrada = base64.b64decode(pacote["chave_sessao_cifrada_b64"])
    assinatura = base64.b64decode(pacote["assinatura_b64"])

    # 2. Romper o Envelope (Decifrar a chave AES usando nossa RSA Privada)
    try:
        chave_aes = rsa_priv_receptor.decrypt(
            chave_sessao_cifrada,
            rsa_padding.OAEP(
                mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
    except Exception:
        raise ValueError("ERRO CRÍTICO: Falha ao abrir o envelope RSA. A mensagem não era para nós.")

    # 3. Decifrar e Validar Integridade da Mensagem (AES-GCM)
    try:
        aesgcm = AESGCM(chave_aes)
        # O Python exige que a tag seja concatenada de volta no final do ciphertext para descriptografar
        msg_bytes = aesgcm.decrypt(nonce, ciphertext + tag, associated_data=None)
    except Exception:
        raise ValueError("ERRO DE INTEGRIDADE: A 'Sombra' adulterou esta mensagem no caminho.")

    # 4. Validar Autenticidade e Não-Repúdio (Assinatura ECDSA)
    try:
        ecdsa_pub_remetente.verify(
            assinatura,
            msg_bytes,
            ec.ECDSA(hashes.SHA256())
        )
    except Exception:
        raise ValueError("ERRO DE AUTENTICIDADE: O carimbo digital é falso. O remetente não é quem diz ser.")

    # Se sobreviveu a todas as validações, a mensagem é 100% segura.
    return msg_bytes.decode('utf-8')