import json
import os

import mensagem

# pasta historico/ na raiz do projeto, um arquivo por subscriber
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "historico")

# quantidade maxima de noticias guardadas por subscriber
LIMITE = 200


def caminho(id_subscriber, pasta=PASTA):
    return os.path.join(pasta, f"{id_subscriber}.json")


def carregar(id_subscriber, pasta=PASTA, ao_falhar=None):
    # devolve as noticias salvas, da mais antiga para a mais nova
    try:
        with open(caminho(id_subscriber, pasta), encoding="utf-8") as f:
            noticias = json.load(f)
    except FileNotFoundError:
        return []
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        # arquivo ilegivel nao derruba a janela, so comeca vazio
        if ao_falhar is not None:
            ao_falhar(str(e))
        return []

    if not isinstance(noticias, list):
        if ao_falhar is not None:
            ao_falhar("o arquivo não contém uma lista")
        return []

    # descarta o que nao for uma noticia valida
    return [n for n in noticias if not mensagem.validar_mensagem(n)]


def adicionar(id_subscriber, msg, pasta=PASTA):
    # devolve False se a noticia ja estava salva
    noticias = carregar(id_subscriber, pasta)
    # o rabbitmq pode entregar de novo uma noticia salva e nao confirmada
    if any(n["id"] == msg["id"] for n in noticias):
        return False

    noticias.append(msg)
    noticias = noticias[-LIMITE:]

    os.makedirs(pasta, exist_ok=True)
    # grava num arquivo temporario e troca, para nao deixar o historico pela metade
    destino = caminho(id_subscriber, pasta)
    temporario = destino + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(noticias, f, ensure_ascii=False, indent=2)
    os.replace(temporario, destino)
    return True
