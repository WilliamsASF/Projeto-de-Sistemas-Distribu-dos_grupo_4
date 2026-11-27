import argparse
import functools
import json
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk

import pika

import config
import logs
import mensagem
import subscriber

# intervalo (ms) entre as leituras da fila de recados
INTERVALO_FILA_MS = 200

# cor da bolinha e texto de cada estado da conexao
ESTADOS = {
    "conectando": ("#e0b000", "Conectando ao broker..."),
    "conectado": ("#2e9e4f", "Conectado"),
    "desconectado": ("#d03030", "Desconectado"),
}

COR_ERRO = "#d03030"


def ler_argumentos():
    parser = argparse.ArgumentParser(description="Janela do subscriber: recebe notícias da exchange noticias.")
    parser.add_argument("--id", required=True, help="identificador do subscriber (nome da fila: fila.<id>)")
    parser.add_argument(
        "--assinar",
        action="append",
        default=[],
        metavar="PADRAO",
        help="categoria permitida ou # (pode ser repetido); sem a flag, não assina nada",
    )
    return parser.parse_args()


def ao_receber(recados, log, canal, metodo, propriedades, corpo):
    # mesma validacao do subscriber de terminal, mas a noticia vai para a fila de recados
    try:
        msg = json.loads(corpo.decode("utf-8"))
        erros = mensagem.validar_mensagem(msg, routing_key=metodo.routing_key)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        erros = [f"corpo não é um JSON válido em UTF-8 ({e})"]

    if erros:
        log.warning(
            "descarte routing_key=%s motivo=%s", metodo.routing_key, "; ".join(erros)
        )
        canal.basic_nack(delivery_tag=metodo.delivery_tag, requeue=False)
        recados.put(("invalida", None))
        return

    recados.put(("noticia", msg))
    canal.basic_ack(delivery_tag=metodo.delivery_tag)
    log.info("entrega id=%s categoria=%s", msg["id"], msg["categoria"])


def consumir(parametros, nome_fila, padroes, recados, log):
    # roda na thread de fundo e nunca mexe na janela, so deixa recados
    try:
        subscriber.preparar_fila(parametros, nome_fila, padroes, log)
        conexao = pika.BlockingConnection(parametros)
        canal = conexao.channel()

        # recebe uma mensagem por vez
        canal.basic_qos(prefetch_count=1)
        canal.basic_consume(
            queue=nome_fila,
            on_message_callback=functools.partial(ao_receber, recados, log),
            auto_ack=False,
        )
        log.info("conexao estado=conectado host=%s port=%s", config.HOST, config.PORT)
        recados.put(("estado", "conectado"))
        canal.start_consuming()
    except pika.exceptions.AMQPError as e:
        log.error("erro_broker detalhe=%r", e)
    recados.put(("estado", "desconectado"))


def hora_local(publicado_em):
    # publicado_em vem em UTC (ex.: 2026-11-17T19:30:00Z)
    data = datetime.fromisoformat(publicado_em.replace("Z", "+00:00"))
    return data.astimezone().strftime("%d/%m %H:%M:%S")


class JanelaSubscriber:
    def __init__(self, raiz, id_subscriber, recados):
        self.raiz = raiz
        self.recados = recados
        self.descartadas = 0
        raiz.title(f"Subscriber {id_subscriber}")
        raiz.geometry("820x520")
        raiz.minsize(600, 360)
        # so a coluna e a linha do feed crescem com a janela
        raiz.columnconfigure(1, weight=1)
        raiz.rowconfigure(1, weight=1)

        # topo: indicador do estado da conexao
        topo = ttk.Frame(raiz, padding=(10, 8))
        topo.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.bolinha = tk.Canvas(topo, width=14, height=14, highlightthickness=0)
        self.bolinha.grid(row=0, column=0, padx=(0, 6))
        self.circulo = self.bolinha.create_oval(2, 2, 13, 13, outline="")
        self.texto_estado = ttk.Label(topo)
        self.texto_estado.grid(row=0, column=1, sticky="w")

        # esquerda: espaco reservado para o painel de assinaturas
        self.painel = ttk.LabelFrame(raiz, text="Assinaturas", padding=10, width=200)
        self.painel.grid(row=1, column=0, sticky="ns", padx=(10, 5), pady=5)
        # mantem a largura mesmo com o painel vazio
        self.painel.grid_propagate(False)

        # direita: feed, com a noticia mais nova em cima
        quadro_feed = ttk.LabelFrame(raiz, text="Feed", padding=5)
        quadro_feed.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=5)
        quadro_feed.columnconfigure(0, weight=1)
        quadro_feed.rowconfigure(0, weight=1)
        self.feed = tk.Text(quadro_feed, wrap="word", state="disabled", padx=8, pady=6)
        self.feed.grid(row=0, column=0, sticky="nsew")
        rolagem = ttk.Scrollbar(quadro_feed, command=self.feed.yview)
        rolagem.grid(row=0, column=1, sticky="ns")
        self.feed.configure(yscrollcommand=rolagem.set)
        self.feed.tag_configure("data", foreground="#777777")
        self.feed.tag_configure("titulo", font=("TkDefaultFont", 11, "bold"))

        # embaixo: barra de status
        self.status = ttk.Label(raiz, anchor="w", padding=(10, 4), relief="sunken")
        self.status.grid(row=2, column=0, columnspan=2, sticky="ew")

        self.definir_estado("conectando")
        raiz.after(INTERVALO_FILA_MS, self.ler_recados)

    def ler_recados(self):
        # roda na thread principal e esvazia a fila deixada pela thread de consumo
        while True:
            try:
                tipo, valor = self.recados.get_nowait()
            except queue.Empty:
                break
            if tipo == "estado":
                self.definir_estado(valor)
            elif tipo == "noticia":
                self.mostrar_noticia(valor)
            elif tipo == "invalida":
                self.descartadas += 1
                self.avisar(f"{self.descartadas} mensagem(ns) inválida(s) descartada(s) (ver log)", erro=True)
        # agenda a proxima leitura
        self.raiz.after(INTERVALO_FILA_MS, self.ler_recados)

    def mostrar_noticia(self, msg):
        # insere no comeco, de baixo para cima, para a mais nova ficar em cima
        self.feed.configure(state="normal")
        self.feed.insert("1.0", f"{msg['resumo']}\n\n")
        self.feed.insert("1.0", f"{msg['titulo']}\n", "titulo")
        self.feed.insert("1.0", f"[{msg['categoria']}] {hora_local(msg['publicado_em'])}\n", "data")
        self.feed.configure(state="disabled")

    def definir_estado(self, estado):
        cor, texto = ESTADOS[estado]
        self.bolinha.itemconfigure(self.circulo, fill=cor)
        self.texto_estado.configure(text=texto)

    def avisar(self, texto, erro=False):
        # mensagem na barra de status, em vermelho quando e erro
        self.status.configure(text=texto, foreground=COR_ERRO if erro else "")


def main():
    args = ler_argumentos()

    # valida id e padroes antes de abrir a janela
    erros = mensagem.validar_id_subscriber(args.id)
    for padrao in args.assinar:
        erros += mensagem.validar_padrao_assinatura(padrao)
    if erros:
        for erro in erros:
            print(f"Erro: {erro}", file=sys.stderr)
        return 1

    log = logs.configurar_logs(f"subscriber.{args.id}")

    padroes = list(dict.fromkeys(args.assinar))
    nome_fila = config.PREFIXO_FILA + args.id

    credenciais = pika.PlainCredentials(config.USUARIO, config.SENHA)
    parametros = pika.ConnectionParameters(
        host=config.HOST, port=config.PORT, credentials=credenciais
    )

    # fila de recados entre a thread de consumo e a janela
    recados = queue.Queue()

    raiz = tk.Tk()
    janela = JanelaSubscriber(raiz, args.id, recados)
    janela.avisar(f"Fila: {nome_fila}")

    # a thread encerra junto com a janela
    thread_consumo = threading.Thread(
        target=consumir, args=(parametros, nome_fila, padroes, recados, log), daemon=True
    )
    thread_consumo.start()

    raiz.mainloop()

    log.info("janela_fechada fila=%s", nome_fila)
    return 0


if __name__ == "__main__":
    sys.exit(main())
