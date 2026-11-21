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

def alterar_binding(parametros, nome_fila, padrao, assinar):
    # conexao curta, so para esta operacao
    conexao = pika.BlockingConnection(parametros)
    try:
        canal = conexao.channel()
        if assinar:
            canal.queue_bind(queue=nome_fila, exchange=config.EXCHANGE, routing_key=padrao)
        else:
            canal.queue_unbind(queue=nome_fila, exchange=config.EXCHANGE, routing_key=padrao)
    finally:
        conexao.close()

def laco_de_comandos(parametros, nome_fila, assinaturas):
    print("Comandos: assinar <padrao>, cancelar <padrao>, listar, sair")
    while True:
        try:
            linha = input("> ")
        except EOFError:
            return

        partes = linha.split()
        if not partes:
            continue
        comando, argumentos = partes[0].lower(), partes[1:]

        if comando == "sair":
            return

        if comando == "listar":
            if assinaturas:
                print(f"Assinaturas ativas: {', '.join(assinaturas)}")
            else:
                print("Nenhuma assinatura ativa.")
            continue

        if comando not in ("assinar", "cancelar"):
            print(f"Comando desconhecido: {comando!r}")
            continue

        if len(argumentos) != 1:
            print(f"Uso: {comando} <padrao>")
            continue

        padrao = argumentos[0]
        erros = mensagem.validar_padrao_assinatura(padrao)
        if erros:
            for erro in erros:
                print(f"Erro: {erro}")
            continue

        if comando == "assinar" and padrao in assinaturas:
            print(f"Você já assina {padrao!r}.")
            continue
        if comando == "cancelar" and padrao not in assinaturas:
            print(f"Você não assina {padrao!r}.")
            continue

        try:
            alterar_binding(parametros, nome_fila, padrao, assinar=(comando == "assinar"))
        except pika.exceptions.AMQPError as e:
            print(f"Erro na comunicação com o broker: {e!r}")
            continue

        if comando == "assinar":
            assinaturas.append(padrao)
            print(f"Assinatura criada: {padrao}")
        else:
            assinaturas.remove(padrao)
            print(f"Assinatura removida: {padrao}")

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

    assinaturas = list(padroes)
    try:
        laco_de_comandos(parametros, nome_fila, assinaturas)
    except KeyboardInterrupt:
        print()
    print("Encerrando (a fila continua no broker).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
