import argparse
import functools
import sys
import tkinter as tk
from tkinter import ttk

import pika

import config
import logs
import mensagem
import subscriber


class PainelAssinaturas:
    def __init__(self, pai, parametros, nome_fila, log, avisar, iniciais=()):
        self.parametros = parametros
        self.nome_fila = nome_fila
        self.log = log
        self.avisar = avisar
        # assinaturas ativas na fila
        self.assinaturas = list(iniciais)

        # uma caixinha por categoria e uma para todas
        opcoes = [(c, c) for c in config.CATEGORIAS] + [(config.PADRAO_TODAS, "Todas (#)")]
        self.marcadas = {}
        self.caixas = []
        for linha, (padrao, rotulo) in enumerate(opcoes):
            marcada = tk.BooleanVar(value=padrao in self.assinaturas)
            caixa = ttk.Checkbutton(
                pai, text=rotulo, variable=marcada,
                command=functools.partial(self.alternar, padrao),
            )
            caixa.grid(row=linha, column=0, sticky="w", pady=2)
            self.marcadas[padrao] = marcada
            self.caixas.append(caixa)

    def habilitar(self, ligado=True):
        for caixa in self.caixas:
            caixa.state(["!disabled"] if ligado else ["disabled"])

    def alternar(self, padrao):
        # a caixinha ja mudou quando o comando roda, entao o valor dela diz o que fazer
        assinar = self.marcadas[padrao].get()
        try:
            subscriber.alterar_binding(self.parametros, self.nome_fila, padrao, assinar=assinar, log=self.log)
        except pika.exceptions.AMQPError as e:
            self.log.error("erro_broker detalhe=%r", e)
            # o broker nao aceitou: a caixinha volta e a lista nao muda
            self.marcadas[padrao].set(not assinar)
            acao = "assinar" if assinar else "cancelar"
            self.avisar(f"Não foi possível {acao} {padrao}", erro=True)
            return

        if assinar:
            self.assinaturas.append(padrao)
            self.avisar(f"Assinatura criada: {padrao}")
        else:
            self.assinaturas.remove(padrao)
            self.avisar(f"Assinatura removida: {padrao}")


def montar_painel(pai, parametros, nome_fila, log, avisar, iniciais=()):
    return PainelAssinaturas(pai, parametros, nome_fila, log, avisar, iniciais)


def main():
    # janela so com o painel, para testar sem a janela do subscriber
    parser = argparse.ArgumentParser(description="Testa o painel de assinaturas sozinho.")
    parser.add_argument("--id", required=True, help="identificador do subscriber (nome da fila: fila.<id>)")
    args = parser.parse_args()

    erros = mensagem.validar_id_subscriber(args.id)
    if erros:
        for erro in erros:
            print(f"Erro: {erro}", file=sys.stderr)
        return 1

    log = logs.configurar_logs(f"assinaturas.{args.id}")
    nome_fila = config.PREFIXO_FILA + args.id
    credenciais = pika.PlainCredentials(config.USUARIO, config.SENHA)
    parametros = pika.ConnectionParameters(
        host=config.HOST, port=config.PORT, credentials=credenciais
    )

    # cria a fila e comeca sem assinaturas, igual ao subscriber
    try:
        subscriber.preparar_fila(parametros, nome_fila, [], log)
    except pika.exceptions.AMQPError as e:
        log.error("conexao estado=falha host=%s port=%s erro=%r", config.HOST, config.PORT, e)
        print(f"Erro na comunicação com o broker: {e!r}", file=sys.stderr)
        return 2

    raiz = tk.Tk()
    raiz.title(f"Assinaturas {args.id}")
    quadro = ttk.LabelFrame(raiz, text="Assinaturas", padding=10)
    quadro.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
    status = ttk.Label(raiz, anchor="w", padding=(10, 4), width=40)
    status.grid(row=1, column=0, sticky="ew")

    def avisar(texto, erro=False):
        status.configure(text=texto, foreground="#d03030" if erro else "")

    montar_painel(quadro, parametros, nome_fila, log, avisar)
    raiz.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
