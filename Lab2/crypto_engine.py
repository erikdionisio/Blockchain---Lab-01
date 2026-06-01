import base64
from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.hazmat.primitives import serialization

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