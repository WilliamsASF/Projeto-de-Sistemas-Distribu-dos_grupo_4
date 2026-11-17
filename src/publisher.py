import argparse
import json
import sys

import pika

import config
import mensagem


def ler_argumentos():
    parser = argparse.ArgumentParser(description="Publica uma notícia na exchange noticias.")
    parser.add_argument("categoria", help="categoria da notícia (usada como routing key)")
    parser.add_argument("titulo", help="título da notícia")
    parser.add_argument("resumo", help="resumo da notícia")
    return parser.parse_args()


def main():
    args = ler_argumentos()

    # monta e valida antes de conectar, se for invalida nao envia nada
    msg = mensagem.criar_mensagem(args.categoria, args.titulo, args.resumo)
    erros = mensagem.validar_mensagem(msg)
    if erros:
        print("Notícia inválida, nada foi enviado:", file=sys.stderr)
        for erro in erros:
            print(f"  - {erro}", file=sys.stderr)
        return 1

    credenciais = pika.PlainCredentials(config.USUARIO, config.SENHA)
    parametros = pika.ConnectionParameters(
        host=config.HOST, port=config.PORT, credentials=credenciais
    )

    try:
        conexao = pika.BlockingConnection(parametros)
    except pika.exceptions.AMQPError as e:
        print(f"Não foi possível conectar ao broker ({config.HOST}:{config.PORT}): {e!r}", file=sys.stderr)
        return 2

    try:
        canal = conexao.channel()

        # exchange duravel do tipo topic (declarar de novo nao gera erro)
        canal.exchange_declare(exchange=config.EXCHANGE, exchange_type="topic", durable=True)

        # espera a confirmacao do broker depois de cada publicacao
        canal.confirm_delivery()

        corpo = json.dumps(msg, ensure_ascii=False).encode("utf-8")

        propriedades = pika.BasicProperties(
            content_type="application/json",
            delivery_mode=pika.DeliveryMode.Persistent,
        )
        canal.basic_publish(
            exchange=config.EXCHANGE,
            routing_key=msg["categoria"],
            body=corpo,
            properties=propriedades,
        )
    except pika.exceptions.AMQPError as e:
        print(f"Erro ao publicar: {e!r}", file=sys.stderr)
        return 2
    finally:
        if conexao.is_open:
            conexao.close()

    print(f"Notícia publicada em {config.EXCHANGE} com routing key {msg['categoria']!r}:")
    print(json.dumps(msg, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
