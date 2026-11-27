import argparse
import sys
import tkinter as tk
from tkinter import ttk

import config
import logs
import mensagem

COR_ERRO = "#d03030"
COR_OK = "#2e9e4f"


def ler_argumentos():
    parser = argparse.ArgumentParser(description="Janela do publisher: publica notícias na exchange noticias.")
    parser.add_argument(
        "--id",
        default="pub",
        help="identificador do publisher, usado nos logs (padrão: pub)",
    )
    return parser.parse_args()


class JanelaPublisher:
    def __init__(self, raiz, id_publisher, log):
        self.raiz = raiz
        self.log = log
        raiz.title(f"Publisher {id_publisher}")
        raiz.minsize(520, 360)
        raiz.columnconfigure(0, weight=1)
        raiz.rowconfigure(0, weight=1)

        form = ttk.Frame(raiz, padding=12)
        form.grid(row=0, column=0, sticky="nsew")
        form.columnconfigure(1, weight=1)
        form.rowconfigure(2, weight=1)

        # categoria: so da para escolher da lista
        ttk.Label(form, text="Categoria").grid(row=0, column=0, sticky="w", pady=4)
        self.categoria = ttk.Combobox(form, values=config.CATEGORIAS, state="readonly", width=20)
        self.categoria.current(0)
        self.categoria.grid(row=0, column=1, sticky="w", pady=4)

        # titulo: campo de uma linha
        ttk.Label(form, text="Título").grid(row=1, column=0, sticky="w", pady=4)
        self.titulo = ttk.Entry(form)
        self.titulo.grid(row=1, column=1, sticky="ew", pady=4)

        # resumo: campo de varias linhas
        ttk.Label(form, text="Resumo").grid(row=2, column=0, sticky="nw", pady=4)
        self.resumo = tk.Text(form, height=6, wrap="word")
        self.resumo.grid(row=2, column=1, sticky="nsew", pady=4)

        self.botao = ttk.Button(form, text="Publicar", command=self.publicar)
        self.botao.grid(row=3, column=1, sticky="e", pady=(8, 4))

        # erros de validacao, embaixo do formulario
        self.erros = ttk.Label(form, foreground=COR_ERRO, justify="left", wraplength=460)
        self.erros.grid(row=4, column=0, columnspan=3, sticky="w")

        # barra de status
        self.status = ttk.Label(raiz, anchor="w", padding=(10, 4), relief="sunken")
        self.status.grid(row=1, column=0, sticky="ew")

        self.titulo.focus_set()

    def publicar(self):
        pass

    def avisar(self, texto, erro=False):
        self.status.configure(text=texto, foreground=COR_ERRO if erro else COR_OK)


def main():
    args = ler_argumentos()

    erros = mensagem.validar_id_subscriber(args.id)
    if erros:
        for erro in erros:
            print(f"Erro: {erro}", file=sys.stderr)
        return 1

    log = logs.configurar_logs(f"publisher.{args.id}")

    raiz = tk.Tk()
    JanelaPublisher(raiz, args.id, log)
    raiz.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
