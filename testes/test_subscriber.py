import io
import os
import sys
import unittest
from unittest import mock

# deixa importar os modulos de src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import subscriber


class TestComandos(unittest.TestCase):
    def rodar(self, linhas, assinaturas=None):
        # roda o laco de comandos com as linhas digitadas e devolve (stdout, assinaturas, chamadas)
        assinaturas = [] if assinaturas is None else assinaturas
        saida = io.StringIO()
        log = mock.Mock()
        with mock.patch("builtins.input", side_effect=linhas), \
                mock.patch.object(subscriber, "alterar_binding") as alterar, \
                mock.patch.object(sys, "stdout", saida):
            try:
                subscriber.laco_de_comandos("params", "fila.sub1", assinaturas, log)
            except StopIteration:
                self.fail("o laço não terminou com o comando sair")
        return saida.getvalue(), assinaturas, alterar.call_args_list

    def test_assinar_cria_binding_e_entra_na_lista(self):
        saida, assinaturas, chamadas = self.rodar(["assinar esportes", "sair"])
        self.assertEqual(assinaturas, ["esportes"])
        self.assertEqual(len(chamadas), 1)
        self.assertEqual(chamadas[0].args[:3], ("params", "fila.sub1", "esportes"))
        self.assertTrue(chamadas[0].kwargs["assinar"])
        self.assertIn("Assinatura criada: esportes", saida)

    def test_cancelar_remove_binding_e_sai_da_lista(self):
        saida, assinaturas, chamadas = self.rodar(["cancelar esportes", "sair"], ["esportes", "cultura"])
        self.assertEqual(assinaturas, ["cultura"])
        self.assertFalse(chamadas[0].kwargs["assinar"])
        self.assertIn("Assinatura removida: esportes", saida)

    def test_assinar_repetido_nao_cria_outro_binding(self):
        saida, _, chamadas = self.rodar(["assinar cultura", "sair"], ["cultura"])
        self.assertEqual(chamadas, [])
        self.assertIn("já assina", saida)

    def test_cancelar_o_que_nao_assina(self):
        saida, _, chamadas = self.rodar(["cancelar cultura", "sair"])
        self.assertEqual(chamadas, [])
        self.assertIn("não assina", saida)

    def test_padrao_invalido_e_recusado(self):
        for padrao in ("futebol", "*", "esportes.*"):
            with self.subTest(padrao=padrao):
                saida, assinaturas, chamadas = self.rodar([f"assinar {padrao}", "sair"])
                self.assertEqual(chamadas, [])
                self.assertEqual(assinaturas, [])
                self.assertIn("Erro:", saida)

    def test_listar(self):
        saida, _, _ = self.rodar(["listar", "sair"], ["esportes", "#"])
        self.assertIn("Assinaturas ativas: esportes, #", saida)
        saida, _, _ = self.rodar(["listar", "sair"])
        self.assertIn("Nenhuma assinatura ativa.", saida)

    def test_comando_desconhecido_e_uso(self):
        saida, _, chamadas = self.rodar(["voar", "assinar", "assinar a b", "", "sair"])
        self.assertEqual(chamadas, [])
        self.assertIn("Comando desconhecido", saida)
        self.assertIn("Uso: assinar <padrao>", saida)

    def test_comando_em_maiusculas_e_espacos_extras(self):
        _, assinaturas, _ = self.rodar(["  ASSINAR   teste  ", "sair"])
        self.assertEqual(assinaturas, ["teste"])

    def test_fim_da_entrada_encerra(self):
        with mock.patch("builtins.input", side_effect=EOFError), \
                mock.patch.object(sys, "stdout", io.StringIO()):
            subscriber.laco_de_comandos("params", "fila.sub1", [], mock.Mock())

    def test_erro_do_broker_nao_muda_a_lista(self):
        import pika
        saida = io.StringIO()
        assinaturas = []
        with mock.patch("builtins.input", side_effect=["assinar teste", "sair"]), \
                mock.patch.object(subscriber, "alterar_binding", side_effect=pika.exceptions.AMQPError("falhou")), \
                mock.patch.object(sys, "stdout", saida):
            subscriber.laco_de_comandos("params", "fila.sub1", assinaturas, mock.Mock())
        self.assertEqual(assinaturas, [])
        self.assertIn("Erro na comunicação com o broker", saida.getvalue())


class TestAoReceber(unittest.TestCase):
    CORPO = (
        b'{"id": "3f2b8c1e-5d4a-4c7e-9b61-0a1d2e3f4a5b", "categoria": "esportes", '
        b'"titulo": "T", "resumo": "R", "publicado_em": "2026-11-17T19:30:00Z"}'
    )

    def chamar(self, corpo, routing_key):
        canal, log = mock.Mock(), mock.Mock()
        metodo = mock.Mock(routing_key=routing_key, delivery_tag=7)
        saida = io.StringIO()
        with mock.patch.object(sys, "stdout", saida):
            subscriber.ao_receber(log, canal, metodo, None, corpo)
        return canal, log, saida.getvalue()

    def test_noticia_valida_e_exibida_confirmada_e_logada(self):
        canal, log, saida = self.chamar(self.CORPO, "esportes")
        self.assertIn("[esportes] T", saida)
        canal.basic_ack.assert_called_once_with(delivery_tag=7)
        canal.basic_nack.assert_not_called()
        log.info.assert_called_once()
        self.assertEqual(log.info.call_args.args[0], "entrega id=%s categoria=%s")
        self.assertEqual(log.info.call_args.args[1:], ("3f2b8c1e-5d4a-4c7e-9b61-0a1d2e3f4a5b", "esportes"))

    def test_routing_key_diferente_e_descartada_com_log(self):
        canal, log, saida = self.chamar(self.CORPO, "cultura")
        canal.basic_nack.assert_called_once_with(delivery_tag=7, requeue=False)
        canal.basic_ack.assert_not_called()
        log.warning.assert_called_once()
        self.assertTrue(log.warning.call_args.args[0].startswith("descarte routing_key="))
        self.assertEqual(saida, "")

    def test_json_quebrado_e_descartado(self):
        canal, log, _ = self.chamar(b"{nao e json", "esportes")
        canal.basic_nack.assert_called_once_with(delivery_tag=7, requeue=False)
        log.warning.assert_called_once()


class TestPrepararFila(unittest.TestCase):
    def preparar(self, padroes):
        # roda preparar_fila com o pika simulado e devolve (conexao, canal)
        conexao = mock.Mock(is_open=True)
        canal = conexao.channel.return_value
        with mock.patch.object(subscriber.pika, "BlockingConnection", return_value=conexao):
            subscriber.preparar_fila("params", "fila.sub1", padroes, mock.Mock())
        return conexao, canal

    def test_limpa_todos_os_padroes_e_cria_so_os_pedidos(self):
        conexao, canal = self.preparar(["esportes", "#"])
        canal.queue_declare.assert_called_once_with(
            queue="fila.sub1", durable=True, exclusive=False, auto_delete=False
        )
        removidos = [c.kwargs["routing_key"] for c in canal.queue_unbind.call_args_list]
        self.assertEqual(removidos, ["tecnologia", "esportes", "cultura", "teste", "#"])
        criados = [c.kwargs["routing_key"] for c in canal.queue_bind.call_args_list]
        self.assertEqual(criados, ["esportes", "#"])
        conexao.close.assert_called_once()

    def test_fecha_a_conexao_mesmo_com_erro(self):
        import pika
        conexao = mock.Mock(is_open=True)
        conexao.channel.return_value.queue_declare.side_effect = pika.exceptions.AMQPError("falhou")
        with mock.patch.object(subscriber.pika, "BlockingConnection", return_value=conexao):
            with self.assertRaises(pika.exceptions.AMQPError):
                subscriber.preparar_fila("params", "fila.sub1", [], mock.Mock())
        conexao.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
