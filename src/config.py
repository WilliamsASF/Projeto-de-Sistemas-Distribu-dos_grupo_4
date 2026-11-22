# parametros de conexao com o broker (credenciais hardcoded, valem so para ambiente local)
HOST = "localhost"
PORT = 5672
USUARIO = "admin"
SENHA = "admin"

# exchange topic onde as noticias sao publicadas
EXCHANGE = "noticias"

# cada subscriber usa uma fila chamada fila.<id>
PREFIXO_FILA = "fila."

# categorias de noticia permitidas
CATEGORIAS = ("tecnologia", "esportes", "cultura")

# routing key usada so para validar a comunicacao basica
CHAVE_TESTE = "teste"

# routing keys aceitas em mensagens e assinaturas
CHAVES_PERMITIDAS = CATEGORIAS + (CHAVE_TESTE,)

# unico wildcard aceito na assinatura
PADRAO_TODAS = "#"

# limites de tamanho em caracteres
MAX_TITULO = 100
MAX_RESUMO = 300
MAX_ID_SUBSCRIBER = 32

# intervalo (em segundos) entre publicacoes no modo repetido do publisher
INTERVALO_REPETIR = 1.0
