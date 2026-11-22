import argparse
import json
import random
import sys

import pika

import config
import logs
import mensagem

# notícias de exemplo do modo repetido, por categoria
NOTICIAS_EXEMPLO = {
    "tecnologia": [
        ("Nova versão do Python é lançada", "A atualização traz melhorias de desempenho e mensagens de erro mais claras."),
        ("Startup apresenta chip de baixo consumo", "O processador promete dobrar a autonomia de dispositivos portáteis."),
        ("Brasil amplia a cobertura de internet 5G", "Mais cidades passam a ter acesso à nova rede móvel."),
    ],
    "esportes": [
        ("Time local vence o clássico", "A partida terminou em 2 a 1, com gol decisivo nos minutos finais."),
        ("Atleta bate recorde nacional", "A marca anterior estava de pé havia mais de dez anos."),
        ("Campeonato estadual tem nova tabela", "A federação divulgou as datas das próximas rodadas."),
    ],
    "cultura": [
        ("Festival de cinema abre inscrições", "Produtores independentes podem enviar filmes até o fim do mês."),
        ("Exposição reúne artistas pernambucanos", "A mostra fica aberta ao público durante todo o mês."),
        ("Orquestra anuncia temporada de concertos", "Os ingressos já estão à venda nos pontos oficiais."),
    ],
}


def ler_argumentos(argv=None):
    parser = argparse.ArgumentParser(
        description="Publica notícias na exchange noticias (uma por execução ou em modo repetido)."
    )
    parser.add_argument("categoria", nargs="?", help="categoria da notícia (usada como routing key)")
    parser.add_argument("titulo", nargs="?", help="título da notícia")
    parser.add_argument("resumo", nargs="?", help="resumo da notícia")
    parser.add_argument(
        "--id",
        default="pub",
        help="identificador do publisher, usado nos logs (padrão: pub)",
    )
    parser.add_argument(
        "--repetir",
        type=int,
        metavar="N",
        help="publica N notícias de exemplo, uma por segundo, em categorias sorteadas",
    )
    args = parser.parse_args(argv)

    if args.repetir is not None:
        if args.repetir < 1:
            parser.error("--repetir precisa ser um número maior que zero")
        if any(v is not None for v in (args.categoria, args.titulo, args.resumo)):
            parser.error("com --repetir não informe categoria, título e resumo")
    elif None in (args.categoria, args.titulo, args.resumo):
        parser.error("informe categoria, título e resumo, ou use --repetir N")
    return args


def conectar(log):
    # abre a conexao e o canal, ja com a exchange declarada e o confirm ligado
    credenciais = pika.PlainCredentials(config.USUARIO, config.SENHA)
    parametros = pika.ConnectionParameters(
        host=config.HOST, port=config.PORT, credentials=credenciais
    )
    conexao = pika.BlockingConnection(parametros)
    log.info("conexao estado=conectado host=%s port=%s", config.HOST, config.PORT)

    canal = conexao.channel()

    # exchange duravel do tipo topic (declarar de novo nao gera erro)
    canal.exchange_declare(exchange=config.EXCHANGE, exchange_type="topic", durable=True)

    # espera a confirmacao do broker depois de cada publicacao
    canal.confirm_delivery()
    return conexao, canal


def desconectar(conexao, log):
    if conexao.is_open:
        conexao.close()
    log.info("conexao estado=desconectado host=%s port=%s", config.HOST, config.PORT)


def publicar(canal, msg, log):
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
    log.info("publicacao id=%s categoria=%s", msg["id"], msg["categoria"])


def montar_noticia_exemplo(id_publisher, numero):
    # sorteia a categoria e uma noticia de exemplo dela
    categoria = random.choice(config.CATEGORIAS)
    titulo, resumo = random.choice(NOTICIAS_EXEMPLO[categoria])
    # o sufixo mostra de qual publisher e de qual envio a noticia veio
    titulo = f"{titulo} [{id_publisher} #{numero}]"
    return mensagem.criar_mensagem(categoria, titulo, resumo)


def publicar_uma(args, log):
    # modo original: uma noticia por execucao
    # monta e valida antes de conectar, se for invalida nao envia nada
    msg = mensagem.criar_mensagem(args.categoria, args.titulo, args.resumo)
    erros = mensagem.validar_mensagem(msg)
    if erros:
        print("Notícia inválida, nada foi enviado:", file=sys.stderr)
        for erro in erros:
            print(f"  - {erro}", file=sys.stderr)
        return 1

    try:
        conexao, canal = conectar(log)
    except pika.exceptions.AMQPError as e:
        log.error("conexao estado=falha host=%s port=%s erro=%r", config.HOST, config.PORT, e)
        print(f"Não foi possível conectar ao broker ({config.HOST}:{config.PORT}): {e!r}", file=sys.stderr)
        return 2

    try:
        publicar(canal, msg, log)
    except pika.exceptions.AMQPError as e:
        log.error("publicacao_falhou id=%s erro=%r", msg["id"], e)
        print(f"Erro ao publicar: {e!r}", file=sys.stderr)
        return 2
    finally:
        desconectar(conexao, log)

    print(f"Notícia publicada em {config.EXCHANGE} com routing key {msg['categoria']!r}:")
    print(json.dumps(msg, ensure_ascii=False, indent=2))
    return 0


def publicar_repetido(args, log):
    # modo repetido: uma conexao so, N noticias, uma por intervalo
    try:
        conexao, canal = conectar(log)
    except pika.exceptions.AMQPError as e:
        log.error("conexao estado=falha host=%s port=%s erro=%r", config.HOST, config.PORT, e)
        print(f"Não foi possível conectar ao broker ({config.HOST}:{config.PORT}): {e!r}", file=sys.stderr)
        return 2

    enviadas = 0
    try:
        for numero in range(1, args.repetir + 1):
            msg = montar_noticia_exemplo(args.id, numero)
            erros = mensagem.validar_mensagem(msg)
            if erros:
                # nao deve acontecer com as noticias de exemplo
                log.error("publicacao_falhou id=%s erro=%s", msg["id"], "; ".join(erros))
                return 1

            publicar(canal, msg, log)
            enviadas += 1
            print(f"[{args.id}] {numero}/{args.repetir} {msg['categoria']}: {msg['titulo']}")

            if numero < args.repetir:
                # conexao.sleep espera sem deixar a conexao parada
                conexao.sleep(config.INTERVALO_REPETIR)
    except KeyboardInterrupt:
        print()
        log.info("interrompido enviadas=%d", enviadas)
    except pika.exceptions.AMQPError as e:
        log.error("publicacao_falhou erro=%r", e)
        print(f"Erro ao publicar: {e!r}", file=sys.stderr)
        return 2
    finally:
        desconectar(conexao, log)

    print(f"{enviadas} notícia(s) publicada(s) por {args.id}.")
    return 0


def main(argv=None):
    args = ler_argumentos(argv)

    erros = mensagem.validar_id_subscriber(args.id)
    if erros:
        for erro in erros:
            print(f"Erro: {erro}", file=sys.stderr)
        return 1

    log = logs.configurar_logs(f"publisher.{args.id}")

    if args.repetir is not None:
        return publicar_repetido(args, log)
    return publicar_uma(args, log)


if __name__ == "__main__":
    sys.exit(main())
