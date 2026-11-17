import re
import uuid
from datetime import datetime, timezone

import config

CAMPOS = ("id", "categoria", "titulo", "resumo", "publicado_em")
REGEX_DATA = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})"
)

REGEX_ID_SUBSCRIBER = re.compile(
    r"[A-Za-z0-9_-]{1,%d}" % config.MAX_ID_SUBSCRIBER
)


def criar_mensagem(categoria, titulo, resumo):
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": str(uuid.uuid4()),
        "categoria": categoria,
        "titulo": titulo,
        "resumo": resumo,
        "publicado_em": agora,
    }


def validar_mensagem(msg, routing_key=None):
    # devolve a lista de erros, vazia se a mensagem for valida
    if not isinstance(msg, dict):
        return ["a mensagem deve ser um objeto JSON"]

    erros = []

    # campos obrigatorios e tipo string
    for campo in CAMPOS:
        if campo not in msg:
            erros.append(f"campo obrigatório ausente: {campo}")
        elif not isinstance(msg[campo], str):
            erros.append(f"o campo {campo} deve ser string")

    def ok(campo):
        return isinstance(msg.get(campo), str)

    if ok("id") and not _uuid_valido(msg["id"]):
        erros.append("o campo id deve ser um UUID")

    if ok("categoria"):
        if msg["categoria"] not in config.CHAVES_PERMITIDAS:
            permitidas = ", ".join(config.CHAVES_PERMITIDAS)
            erros.append(f"categoria não permitida (use: {permitidas})")
        elif routing_key is not None and msg["categoria"] != routing_key:
            erros.append(
                f"categoria {msg['categoria']!r} diferente da routing key {routing_key!r}"
            )

    if ok("titulo"):
        erros += _validar_texto("titulo", msg["titulo"], config.MAX_TITULO)

    if ok("resumo"):
        erros += _validar_texto("resumo", msg["resumo"], config.MAX_RESUMO)

    if ok("publicado_em") and not _data_valida(msg["publicado_em"]):
        erros.append("o campo publicado_em deve estar em ISO 8601 (ex.: 2026-11-17T19:30:00Z)")

    return erros


def validar_padrao_assinatura(padrao):
    # aceita categoria permitida ou #
    if not isinstance(padrao, str):
        return ["o padrão de assinatura deve ser string"]
    if padrao == config.PADRAO_TODAS or padrao in config.CHAVES_PERMITIDAS:
        return []
    permitidas = ", ".join(config.CHAVES_PERMITIDAS)
    return [f"padrão inválido: {padrao!r} (use uma categoria permitida ({permitidas}) ou #)"]


def validar_id_subscriber(id_subscriber):
    if not isinstance(id_subscriber, str):
        return ["o id deve ser string"]
    if not REGEX_ID_SUBSCRIBER.fullmatch(id_subscriber):
        return [
            f"id inválido: {id_subscriber!r} "
            f"(use letras, dígitos, - e _, de 1 a {config.MAX_ID_SUBSCRIBER} caracteres)"
        ]
    return []


def _validar_texto(campo, valor, limite):
    if not valor.strip():
        return [f"o campo {campo} não pode ser vazio"]
    if len(valor) > limite:
        return [f"o campo {campo} passa de {limite} caracteres ({len(valor)})"]
    return []


def _uuid_valido(valor):
    try:
        return str(uuid.UUID(valor)) == valor.lower()
    except ValueError:
        return False


def _data_valida(valor):
    if not REGEX_DATA.fullmatch(valor):
        return False
    if valor.endswith("Z"):
        valor = valor[:-1] + "+00:00"
    try:
        datetime.fromisoformat(valor)
    except ValueError:
        return False
    return True
