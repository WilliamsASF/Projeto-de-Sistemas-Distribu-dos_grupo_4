import logging
import sys

# formato combinado entre publisher e subscriber:
# data, nivel, nome do cliente e mensagem
FORMATO = "%(asctime)s %(levelname)s %(name)s %(message)s"
FORMATO_DATA = "%Y-%m-%d %H:%M:%S"


def configurar_logs(nome, nivel=logging.INFO):
    # devolve um logger com o nome do cliente (ex.: publisher.pub1)
    # os logs vao para o stderr, o stdout fica so com o que e mostrado ao usuario
    logger = logging.getLogger(nome)
    logger.setLevel(nivel)
    logger.propagate = False

    # chamar de novo com o mesmo nome nao duplica as linhas
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(FORMATO, FORMATO_DATA))
        logger.addHandler(handler)
    return logger
