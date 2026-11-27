import functools
import tkinter as tk
from tkinter import ttk

import pika

import config
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
