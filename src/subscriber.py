import argparse
import json
import sys
import threading

import pika

import config
import mensagem


def ler_argumentos():
    parser = argparse.ArgumentParser(description="Recebe notícias da exchange noticias.")
    parser.add_argument("--id", required=True, help="identificador do subscriber (nome da fila: fila.<id>)")
    parser.add_argument(
        "--assinar",
        action="append",
        default=[],
        metavar="PADRAO",
        help="categoria permitida ou # (pode ser repetido); sem a flag, não assina nada",
    )
    return parser.parse_args()


def ao_receber(canal, metodo, propriedades, corpo):
    # converte o corpo, se falhar tá inválida
    try:
        msg = json.loads(corpo.decode("utf-8"))
        erros = mensagem.validar_mensagem(msg, routing_key=metodo.routing_key)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        erros = [f"corpo não é um JSON válido em UTF-8 ({e})"]

    if erros:
        # descarta sem colocar na fila
        print(f"[aviso] mensagem inválida descartada (routing key {metodo.routing_key!r}):")
        for erro in erros:
            print(f"  - {erro}")
        canal.basic_nack(delivery_tag=metodo.delivery_tag, requeue=False)
        return

    print(f"[{msg['categoria']}] {msg['titulo']}")
    print(f"    {msg['resumo']}")

    canal.basic_ack(delivery_tag=metodo.delivery_tag)

def consumir(nome_fila, parametros):
    # roda na thread de fundo
    try:
        conexao = pika.BlockingConnection(parametros)
        canal = conexao.channel()

        # recebe uma mensagem por vez
        canal.basic_qos(prefetch_count=1)
        canal.basic_consume(queue=nome_fila, on_message_callback=ao_receber, auto_ack=False)
        canal.start_consuming()
    except pika.exceptions.AMQPError as e:
        print(f"Erro na comunicação com o broker: {e!r}", file=sys.stderr)

def main():
    args = ler_argumentos()

    # valida id e padroes antes de conectar
    erros = mensagem.validar_id_subscriber(args.id)
    for padrao in args.assinar:
        erros += mensagem.validar_padrao_assinatura(padrao)
    if erros:
        for erro in erros:
            print(f"Erro: {erro}", file=sys.stderr)
        return 1

    padroes = list(dict.fromkeys(args.assinar))
    nome_fila = config.PREFIXO_FILA + args.id

    credenciais = pika.PlainCredentials(config.USUARIO, config.SENHA)
    parametros = pika.ConnectionParameters(
        host=config.HOST, port=config.PORT, credentials=credenciais
    )

    conexao = None
    try:
        conexao = pika.BlockingConnection(parametros)
        canal = conexao.channel()

        canal.exchange_declare(exchange=config.EXCHANGE, exchange_type="topic", durable=True)

        canal.queue_declare(queue=nome_fila, durable=True, exclusive=False, auto_delete=False)

        # remove assinaturas antigas
        for padrao in config.CHAVES_PERMITIDAS + (config.PADRAO_TODAS,):
            canal.queue_unbind(queue=nome_fila, exchange=config.EXCHANGE, routing_key=padrao)

        # 1 binding por padrao
        for padrao in padroes:
            canal.queue_bind(queue=nome_fila, exchange=config.EXCHANGE, routing_key=padrao)
    except pika.exceptions.AMQPError as e:
        print(f"Erro na comunicação com o broker: {e!r}", file=sys.stderr)
        return 2
    finally:
        if conexao is not None and conexao.is_open:
            conexao.close()

    print(f"Subscriber {args.id!r} conectado. Fila: {nome_fila}")
    if padroes:
        print(f"Assinaturas pedidas: {', '.join(padroes)}")
    else:
        print("Nenhuma categoria assinada nesta execução.")
    print("Aguardando notícias (Ctrl+C para sair).")

    # a thread encerra com o programa
    thread_consumo = threading.Thread(target=consumir, args=(nome_fila, parametros), daemon=True)
    thread_consumo.start()

    try:
        while thread_consumo.is_alive():
            thread_consumo.join(timeout=1)
    except KeyboardInterrupt:
        print("\nEncerrando (a fila continua no broker).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
