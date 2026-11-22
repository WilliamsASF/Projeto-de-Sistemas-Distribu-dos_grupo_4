import os
import sys
import unittest
from unittest import mock

# deixa importar os modulos de src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config
import mensagem
import publisher


class TestArgumentos(unittest.TestCase):
    def ler(self, *argv):
        # argparse chama sys.exit em erro, o stderr e silenciado para nao poluir os testes
        with mock.patch.object(sys, "stderr"):
            return publisher.ler_argumentos(list(argv))

    def test_modo_unico(self):
        args = self.ler("tecnologia", "Título", "Resumo")
        self.assertEqual((args.categoria, args.titulo, args.resumo), ("tecnologia", "Título", "Resumo"))
        self.assertIsNone(args.repetir)
        self.assertEqual(args.id, "pub")

    def test_modo_unico_com_id(self):
        args = self.ler("--id", "pub1", "cultura", "T", "R")
        self.assertEqual(args.id, "pub1")

    def test_modo_repetido(self):
        args = self.ler("--id", "pub1", "--repetir", "10")
        self.assertEqual(args.repetir, 10)
        self.assertEqual(args.id, "pub1")

    def test_sem_nada_e_erro(self):
        with self.assertRaises(SystemExit):
            self.ler()

    def test_modo_unico_incompleto_e_erro(self):
        with self.assertRaises(SystemExit):
            self.ler("tecnologia", "Só o título")

    def test_repetir_com_noticia_e_erro(self):
        with self.assertRaises(SystemExit):
            self.ler("--repetir", "3", "tecnologia", "T", "R")

    def test_repetir_zero_ou_negativo_e_erro(self):
        for valor in ("0", "-2"):
            with self.subTest(valor=valor), self.assertRaises(SystemExit):
                self.ler("--repetir", valor)

    def test_repetir_nao_numerico_e_erro(self):
        with self.assertRaises(SystemExit):
            self.ler("--repetir", "abc")


class TestNoticiasExemplo(unittest.TestCase):
    def test_cobre_todas_as_categorias(self):
        self.assertEqual(set(publisher.NOTICIAS_EXEMPLO), set(config.CATEGORIAS))

    def test_todas_as_noticias_de_exemplo_sao_validas(self):
        for categoria, noticias in publisher.NOTICIAS_EXEMPLO.items():
            self.assertTrue(noticias)
            for titulo, resumo in noticias:
                msg = mensagem.criar_mensagem(categoria, titulo, resumo)
                self.assertEqual(mensagem.validar_mensagem(msg), [], (categoria, titulo))

    def test_noticia_montada_e_valida_e_so_de_categoria_de_noticia(self):
        for numero in range(1, 60):
            msg = publisher.montar_noticia_exemplo("pub1", numero)
            self.assertEqual(mensagem.validar_mensagem(msg), [])
            self.assertIn(msg["categoria"], config.CATEGORIAS)
            self.assertIn(f"[pub1 #{numero}]", msg["titulo"])

    def test_sorteio_usa_mais_de_uma_categoria(self):
        categorias = {publisher.montar_noticia_exemplo("pub1", n)["categoria"] for n in range(80)}
        self.assertGreater(len(categorias), 1)


if __name__ == "__main__":
    unittest.main()
