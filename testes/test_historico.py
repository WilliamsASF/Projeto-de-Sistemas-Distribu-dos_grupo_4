import json
import os
import sys
import tempfile
import unittest
from unittest import mock

# deixa importar os modulos de src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import historico
import mensagem


def noticia(titulo="Titulo"):
    return mensagem.criar_mensagem("esportes", titulo, "Resumo")


class TestHistorico(unittest.TestCase):
    def setUp(self):
        # cada teste usa uma pasta temporaria propria
        self.temp = tempfile.TemporaryDirectory()
        self.pasta = self.temp.name

    def tearDown(self):
        self.temp.cleanup()

    def test_sem_arquivo_comeca_vazio(self):
        self.assertEqual(historico.carregar("sub1", self.pasta), [])

    def test_adicionar_e_carregar_na_ordem(self):
        primeira, segunda = noticia("Primeira"), noticia("Segunda")
        self.assertTrue(historico.adicionar("sub1", primeira, self.pasta))
        self.assertTrue(historico.adicionar("sub1", segunda, self.pasta))
        self.assertEqual(historico.carregar("sub1", self.pasta), [primeira, segunda])

    def test_noticia_repetida_e_ignorada(self):
        msg = noticia()
        historico.adicionar("sub1", msg, self.pasta)
        self.assertFalse(historico.adicionar("sub1", msg, self.pasta))
        self.assertEqual(len(historico.carregar("sub1", self.pasta)), 1)

    def test_guarda_so_as_mais_recentes(self):
        msgs = [noticia(f"Noticia {i}") for i in range(historico.LIMITE + 5)]
        for msg in msgs:
            historico.adicionar("sub1", msg, self.pasta)
        salvas = historico.carregar("sub1", self.pasta)
        self.assertEqual(len(salvas), historico.LIMITE)
        self.assertEqual(salvas[0], msgs[5])
        self.assertEqual(salvas[-1], msgs[-1])

    def test_cada_subscriber_tem_seu_arquivo(self):
        historico.adicionar("sub1", noticia(), self.pasta)
        self.assertEqual(historico.carregar("sub2", self.pasta), [])
        self.assertTrue(os.path.exists(os.path.join(self.pasta, "sub1.json")))

    def test_cria_a_pasta_se_nao_existir(self):
        pasta = os.path.join(self.pasta, "nova")
        historico.adicionar("sub1", noticia(), pasta)
        self.assertEqual(len(historico.carregar("sub1", pasta)), 1)

    def test_arquivo_ilegivel_comeca_vazio_e_avisa(self):
        with open(os.path.join(self.pasta, "sub1.json"), "w", encoding="utf-8") as f:
            f.write("{nao e json")
        ao_falhar = mock.Mock()
        self.assertEqual(historico.carregar("sub1", self.pasta, ao_falhar), [])
        ao_falhar.assert_called_once()

    def test_arquivo_que_nao_e_lista_comeca_vazio(self):
        with open(os.path.join(self.pasta, "sub1.json"), "w", encoding="utf-8") as f:
            json.dump({"id": "x"}, f)
        ao_falhar = mock.Mock()
        self.assertEqual(historico.carregar("sub1", self.pasta, ao_falhar), [])
        ao_falhar.assert_called_once()

    def test_itens_invalidos_sao_descartados(self):
        valida = noticia()
        with open(os.path.join(self.pasta, "sub1.json"), "w", encoding="utf-8") as f:
            json.dump([{"titulo": "sem os outros campos"}, valida], f)
        self.assertEqual(historico.carregar("sub1", self.pasta), [valida])

    def test_depois_de_arquivo_ilegivel_volta_a_salvar(self):
        with open(os.path.join(self.pasta, "sub1.json"), "w", encoding="utf-8") as f:
            f.write("{nao e json")
        msg = noticia()
        self.assertTrue(historico.adicionar("sub1", msg, self.pasta))
        self.assertEqual(historico.carregar("sub1", self.pasta), [msg])


if __name__ == "__main__":
    unittest.main()
