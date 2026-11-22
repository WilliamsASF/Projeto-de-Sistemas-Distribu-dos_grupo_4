import io
import logging
import os
import re
import sys
import unittest
from unittest import mock

# deixa importar os modulos de src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import logs


class TestConfigurarLogs(unittest.TestCase):
    def novo_logger(self, nome):
        saida = io.StringIO()
        with mock.patch.object(sys, "stderr", saida):
            log = logs.configurar_logs(nome)
        self.addCleanup(lambda: log.handlers.clear())
        return log, saida

    def test_formato_com_data_nivel_nome_e_mensagem(self):
        log, saida = self.novo_logger("publisher.teste_formato")
        log.info("publicacao id=%s categoria=%s", "abc", "esportes")
        linha = saida.getvalue().strip()
        padrao = (
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} INFO "
            r"publisher\.teste_formato publicacao id=abc categoria=esportes"
        )
        self.assertRegex(linha, "^" + padrao + "$")

    def test_nivel_aparece_no_log(self):
        log, saida = self.novo_logger("subscriber.teste_nivel")
        log.warning("descarte routing_key=x motivo=y")
        self.assertIn(" WARNING subscriber.teste_nivel ", saida.getvalue())

    def test_chamar_duas_vezes_nao_duplica_linhas(self):
        log, saida = self.novo_logger("publisher.teste_duplicado")
        with mock.patch.object(sys, "stderr", saida):
            logs.configurar_logs("publisher.teste_duplicado")
        log.info("uma vez")
        self.assertEqual(len(saida.getvalue().strip().splitlines()), 1)

    def test_nao_propaga_para_o_logger_raiz(self):
        log, _ = self.novo_logger("publisher.teste_propaga")
        self.assertFalse(log.propagate)

    def test_logs_vao_para_o_stderr_e_nao_para_o_stdout(self):
        saida_out = io.StringIO()
        with mock.patch.object(sys, "stdout", saida_out):
            log, saida_err = self.novo_logger("publisher.teste_stderr")
            log.info("evento")
        self.assertEqual(saida_out.getvalue(), "")
        self.assertIn("evento", saida_err.getvalue())


if __name__ == "__main__":
    unittest.main()
