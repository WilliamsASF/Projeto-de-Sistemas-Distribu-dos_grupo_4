import argparse
import sys
import tkinter as tk
from tkinter import ttk

import pika

import config
import logs
import mensagem
import publisher

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
        self.texto_titulo = tk.StringVar()
        self.titulo = ttk.Entry(form, textvariable=self.texto_titulo)
        self.titulo.grid(row=1, column=1, sticky="ew", pady=4)
        self.contador_titulo = ttk.Label(form, width=8, anchor="e")
        self.contador_titulo.grid(row=1, column=2, sticky="e", padx=(6, 0))
        self.texto_titulo.trace_add("write", lambda *_: self.atualizar_contadores())

        # resumo: campo de varias linhas
        ttk.Label(form, text="Resumo").grid(row=2, column=0, sticky="nw", pady=4)
        self.resumo = tk.Text(form, height=6, wrap="word")
        self.resumo.grid(row=2, column=1, sticky="nsew", pady=4)
        self.contador_resumo = ttk.Label(form, width=8, anchor="e")
        self.contador_resumo.grid(row=2, column=2, sticky="ne", padx=(6, 0), pady=4)
        self.resumo.bind("<<Modified>>", self.resumo_mudou)

        self.botao = ttk.Button(form, text="Publicar", command=self.publicar)
        self.botao.grid(row=3, column=1, sticky="e", pady=(8, 4))

        # erros de validacao, embaixo do formulario
        self.erros = ttk.Label(form, foreground=COR_ERRO, justify="left", wraplength=460)
        self.erros.grid(row=4, column=0, columnspan=3, sticky="w")

        # barra de status
        self.status = ttk.Label(raiz, anchor="w", padding=(10, 4), relief="sunken")
        self.status.grid(row=1, column=0, sticky="ew")

        self.atualizar_contadores()
        self.titulo.focus_set()

    def texto_resumo(self):
        # o Text sempre termina com uma quebra de linha extra
        return self.resumo.get("1.0", "end-1c")

    def resumo_mudou(self, evento):
        self.atualizar_contadores()
        # desliga a flag para o proximo <<Modified>> disparar
        self.resumo.edit_modified(False)

    def atualizar_contadores(self):
        for contador, texto, limite in (
            (self.contador_titulo, self.texto_titulo.get(), config.MAX_TITULO),
            (self.contador_resumo, self.texto_resumo(), config.MAX_RESUMO),
        ):
            # fica vermelho quando passa do limite
            contador.configure(
                text=f"{len(texto)}/{limite}",
                foreground=COR_ERRO if len(texto) > limite else "",
            )

    def montar_noticia(self):
        # monta e valida antes de conectar, se for invalida mostra os erros e nao envia
        msg = mensagem.criar_mensagem(
            self.categoria.get(), self.texto_titulo.get().strip(), self.texto_resumo().strip()
        )
        erros = mensagem.validar_mensagem(msg)
        if erros:
            self.erros.configure(text="\n".join(f"- {erro}" for erro in erros))
            return None
        self.erros.configure(text="")
        return msg

    def publicar(self):
        msg = self.montar_noticia()
        if msg is None:
            return

        # uma conexao por clique, como no publisher de terminal
        try:
            conexao, canal = publisher.conectar(self.log)
        except pika.exceptions.AMQPError as e:
            self.log.error("conexao estado=falha host=%s port=%s erro=%r", config.HOST, config.PORT, e)
            self.avisar(f"Não foi possível conectar ao broker ({config.HOST}:{config.PORT})", erro=True)
            return

        try:
            publisher.publicar(canal, msg, self.log)
        except pika.exceptions.NackError as e:
            # o confirm_delivery levanta essa excecao quando o broker recusa
            self.log.error("publicacao_falhou id=%s erro=%r", msg["id"], e)
            self.avisar("O broker não confirmou a notícia", erro=True)
            return
        except pika.exceptions.AMQPError as e:
            self.log.error("publicacao_falhou id=%s erro=%r", msg["id"], e)
            self.avisar(f"Erro na comunicação com o broker: {e!r}", erro=True)
            return
        finally:
            publisher.desconectar(conexao, self.log)

        self.avisar(f"Publicada: {msg['titulo']}")
        # limpa titulo e resumo e mantem a categoria
        self.texto_titulo.set("")
        self.resumo.delete("1.0", "end")
        self.titulo.focus_set()

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
