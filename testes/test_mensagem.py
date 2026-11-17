import os
import sys
import unittest

# deixa importar os modulos de src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import mensagem


def msg_valida(**mudancas):
    # mensagem valida de base, com campos trocados conforme o teste
    base = {
        "id": "3f2b8c1e-5d4a-4c7e-9b61-0a1d2e3f4a5b",
        "categoria": "tecnologia",
        "titulo": "Título de teste",
        "resumo": "Resumo de teste.",
        "publicado_em": "2026-11-17T19:30:00Z",
    }
    base.update(mudancas)
    return base


class TestCriarMensagem(unittest.TestCase):
    def test_mensagem_criada_e_valida(self):
        msg = mensagem.criar_mensagem("esportes", "Título", "Resumo")
        self.assertEqual(mensagem.validar_mensagem(msg), [])
        self.assertEqual(msg["categoria"], "esportes")

    def test_data_em_utc_com_sufixo_z(self):
        msg = mensagem.criar_mensagem("cultura", "Título", "Resumo")
        self.assertTrue(msg["publicado_em"].endswith("Z"))

    def test_ids_diferentes(self):
        a = mensagem.criar_mensagem("cultura", "t", "r")
        b = mensagem.criar_mensagem("cultura", "t", "r")
        self.assertNotEqual(a["id"], b["id"])


class TestValidarMensagem(unittest.TestCase):
    def test_valida(self):
        self.assertEqual(mensagem.validar_mensagem(msg_valida()), [])

    def test_todas_as_categorias_permitidas(self):
        for categoria in ("tecnologia", "esportes", "cultura", "teste"):
            with self.subTest(categoria=categoria):
                self.assertEqual(mensagem.validar_mensagem(msg_valida(categoria=categoria)), [])

    def test_nao_e_objeto(self):
        for valor in (None, [], "texto", 42):
            with self.subTest(valor=valor):
                self.assertNotEqual(mensagem.validar_mensagem(valor), [])

    def test_campo_ausente(self):
        for campo in mensagem.CAMPOS:
            with self.subTest(campo=campo):
                msg = msg_valida()
                del msg[campo]
                erros = mensagem.validar_mensagem(msg)
                self.assertEqual(len(erros), 1)
                self.assertIn(campo, erros[0])

    def test_campo_que_nao_e_string(self):
        for campo in mensagem.CAMPOS:
            for valor in (123, None, ["a"], True):
                with self.subTest(campo=campo, valor=valor):
                    erros = mensagem.validar_mensagem(msg_valida(**{campo: valor}))
                    self.assertNotEqual(erros, [])

    def test_id_invalido(self):
        invalidos = [
            "",
            "abc",
            "3f2b8c1e5d4a4c7e9b610a1d2e3f4a5b",
            "{3f2b8c1e-5d4a-4c7e-9b61-0a1d2e3f4a5b}",
            "urn:uuid:3f2b8c1e-5d4a-4c7e-9b61-0a1d2e3f4a5b",
        ]
        for valor in invalidos:
            with self.subTest(valor=valor):
                self.assertNotEqual(mensagem.validar_mensagem(msg_valida(id=valor)), [])

    def test_id_valido_em_maiusculas(self):
        id_maiusculo = "3F2B8C1E-5D4A-4C7E-9B61-0A1D2E3F4A5B"
        self.assertEqual(mensagem.validar_mensagem(msg_valida(id=id_maiusculo)), [])

    def test_categoria_nao_permitida(self):
        for valor in ("politica", "Tecnologia", "", "#", "*", "tecnologia.ia"):
            with self.subTest(valor=valor):
                self.assertNotEqual(mensagem.validar_mensagem(msg_valida(categoria=valor)), [])

    def test_categoria_diferente_da_routing_key(self):
        msg = msg_valida(categoria="tecnologia")
        self.assertEqual(mensagem.validar_mensagem(msg, routing_key="tecnologia"), [])
        erros = mensagem.validar_mensagem(msg, routing_key="esportes")
        self.assertEqual(len(erros), 1)
        self.assertIn("routing key", erros[0])

    def test_titulo_vazio_ou_so_espacos(self):
        for valor in ("", "   ", "\t\n"):
            with self.subTest(valor=valor):
                self.assertNotEqual(mensagem.validar_mensagem(msg_valida(titulo=valor)), [])

    def test_titulo_no_limite(self):
        self.assertEqual(mensagem.validar_mensagem(msg_valida(titulo="a" * 100)), [])
        self.assertNotEqual(mensagem.validar_mensagem(msg_valida(titulo="a" * 101)), [])

    def test_resumo_vazio_ou_so_espacos(self):
        for valor in ("", "   "):
            with self.subTest(valor=valor):
                self.assertNotEqual(mensagem.validar_mensagem(msg_valida(resumo=valor)), [])

    def test_resumo_no_limite(self):
        self.assertEqual(mensagem.validar_mensagem(msg_valida(resumo="a" * 300)), [])
        self.assertNotEqual(mensagem.validar_mensagem(msg_valida(resumo="a" * 301)), [])

    def test_data_valida(self):
        validas = [
            "2026-11-17T19:30:00Z",
            "2026-11-17T19:30:00.123Z",
            "2026-11-17T19:30:00+00:00",
            "2026-11-17T16:30:00-03:00",
        ]
        for valor in validas:
            with self.subTest(valor=valor):
                self.assertEqual(mensagem.validar_mensagem(msg_valida(publicado_em=valor)), [])

    def test_data_invalida(self):
        invalidas = [
            "",
            "ontem",
            "2026-11-17",
            "2026-11-17 19:30:00Z",
            "2026-11-17T19:30:00",
            "2026-13-17T19:30:00Z",
            "2026-11-31T19:30:00Z",
            "2026-11-17T25:30:00Z",
            "17/11/2026",
        ]
        for valor in invalidas:
            with self.subTest(valor=valor):
                self.assertNotEqual(mensagem.validar_mensagem(msg_valida(publicado_em=valor)), [])

    def test_campos_extras_sao_ignorados(self):
        self.assertEqual(mensagem.validar_mensagem(msg_valida(autor="alguém", extra=1)), [])

    def test_varios_erros_de_uma_vez(self):
        erros = mensagem.validar_mensagem({"categoria": "politica", "titulo": ""})
        # faltam id, resumo e publicado_em, e categoria e titulo sao invalidos
        self.assertEqual(len(erros), 5)


class TestValidarPadraoAssinatura(unittest.TestCase):
    def test_padroes_validos(self):
        for padrao in ("tecnologia", "esportes", "cultura", "teste", "#"):
            with self.subTest(padrao=padrao):
                self.assertEqual(mensagem.validar_padrao_assinatura(padrao), [])

    def test_padroes_invalidos(self):
        invalidos = ["*", "", "esporte", "Esportes", "tecnologia.*", "#.x", "*.#", "tecnologia ", "politica"]
        for padrao in invalidos:
            with self.subTest(padrao=padrao):
                self.assertNotEqual(mensagem.validar_padrao_assinatura(padrao), [])

    def test_nao_string(self):
        for padrao in (None, 1, ["#"]):
            with self.subTest(padrao=padrao):
                self.assertNotEqual(mensagem.validar_padrao_assinatura(padrao), [])


class TestValidarIdSubscriber(unittest.TestCase):
    def test_ids_validos(self):
        for valor in ("a", "ana", "sub-1", "sub_1", "ABC123", "a" * 32):
            with self.subTest(valor=valor):
                self.assertEqual(mensagem.validar_id_subscriber(valor), [])

    def test_ids_invalidos(self):
        invalidos = ["", "a" * 33, "com espaco", "ponto.no.meio", "acentuação", "a/b", "a\n", "#", "*"]
        for valor in invalidos:
            with self.subTest(valor=valor):
                self.assertNotEqual(mensagem.validar_id_subscriber(valor), [])

    def test_nao_string(self):
        self.assertNotEqual(mensagem.validar_id_subscriber(None), [])


if __name__ == "__main__":
    unittest.main()
