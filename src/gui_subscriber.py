import argparse
import sys
import tkinter as tk
from tkinter import ttk

import pika

import config
import logs
import mensagem

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


class JanelaSubscriber:
    def __init__(self, raiz, id_subscriber):
        self.raiz = raiz
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

        # embaixo: barra de status
        self.status = ttk.Label(raiz, anchor="w", padding=(10, 4), relief="sunken")
        self.status.grid(row=2, column=0, columnspan=2, sticky="ew")

        self.definir_estado("conectando")

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

    raiz = tk.Tk()
    janela = JanelaSubscriber(raiz, args.id)
    janela.avisar(f"Fila: {nome_fila}")
    raiz.mainloop()

    log.info("janela_fechada fila=%s", nome_fila)
    return 0


if __name__ == "__main__":
    sys.exit(main())
