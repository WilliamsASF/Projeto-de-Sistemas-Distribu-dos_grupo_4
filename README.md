# Feed de Notícias em Tempo Real com Publish/Subscribe

- Disciplina: CIN0143, Sistemas Distribuídos (CIn-UFPE)
- Docente: David J M Cavalcanti
- Equipe: 04
- Tema: Publish/Subscribe com Message Broker
- Entrega: 2

| Integrante                         | Logins CIn |
| ---------------------------------- | ---------- |
| Caíque Machado Sena de Oliveira    | cmso       |
| João Gabriel Medeiros Caldas       | jgmc       |
| Ricardo Cunha Lira                 | rcl4       |
| Vinicius Lauter Figuerêdo Oliveira | vlfo       |
| Williams Andrade de Souza Filho    | wasf       |

## 1. Descrição do projeto

O sistema é um feed de notícias em tempo real. Publicadores publicam notícias categorizadas (por exemplo, tecnologia, esportes e cultura) em um broker. Inscritos assinam categorias, recebem título e resumo de forma assíncrona e podem mudar as assinaturas em tempo de execução. Não existe servidor central acoplado aos clientes.

Os clientes rodam no terminal. O publisher envia uma notícia com categoria, título e resumo para o broker. O subscriber digita comandos para assinar ou cancelar categorias e vê no terminal o título e o resumo das notícias que chegam. Na Entrega 2, o subscriber aceita os comandos `assinar`, `cancelar`, `listar` e `sair` enquanto continua recebendo notícias, e os dois clientes escrevem logs de conexão, publicação, entrega e assinaturas. O publisher também tem um modo repetido, para rodar vários publishers ao mesmo tempo.

## 2. Decisão tecnológica

Broker escolhido: RabbitMQ

Justificativa:

- Pub/sub: o RabbitMQ funciona com exchanges. O publisher manda a notícia para a exchange com a categoria como routing key, sem saber quem vai receber. A exchange do tipo topic encaminha a mensagem para as filas que assinaram aquela categoria. Por isso, o filtro por categoria é feito pelo próprio broker.
- Sem servidor central acoplado aos clientes: publishers e subscribers só se conectam ao broker e não se conhecem. Cada subscriber tem a sua fila, então um subscriber parado não atrapalha os outros.
- Assinatura dinâmica: assinar uma categoria é criar um binding da fila do subscriber na exchange, e cancelar é remover esse binding. O cliente faz isso direto no broker enquanto está rodando, sem precisar reiniciar nada.
- Ambiente local: a imagem `rabbitmq:4-management` já vem com a interface web, onde dá para ver exchanges, filas e bindings. Isso ajuda a mostrar as evidências da validação.

Essas características foram tiradas da documentação do RabbitMQ. Na Entrega 1, foram verificados o roteamento por categoria na exchange topic, a fila própria de cada subscriber e a criação de bindings ao iniciar o subscriber (seção 10). Na Entrega 2, assinar e cancelar passaram a ser feitos por comandos em tempo de execução (seção 7), e o roteiro da validação com vários clientes está na seção 10.

Linguagem e biblioteca cliente: Python 3 com pika client.

## 3. Arquitetura

```mermaid
flowchart LR
    P1["Publisher 1"] --> EX
    P2["Publisher N"] --> EX
    subgraph BROKER["Broker (RabbitMQ)"]
        EX{{"Exchange: noticias (topic)"}}
        Q1["Fila do subscriber 1"]
        Q2["Fila do subscriber N"]
        EX -- "binding por categoria" --> Q1
        EX -- "binding por categoria" --> Q2
    end
    Q1 --> S1["Subscriber 1"]
    Q2 --> S2["Subscriber N"]
```

Responsabilidades:

- Publisher: monta a notícia (categoria, título e resumo) e publica na exchange `noticias`, usando a categoria como routing key. Ele não sabe quantos subscribers existem nem quem vai receber a mensagem.
- Broker: recebe as mensagens na exchange e entrega uma cópia para cada fila que tem um binding compatível com a routing key. É o único ponto em comum entre publishers e subscribers, mas não tem regra de negócio da aplicação.
- Subscriber: cria a própria fila, cria e remove bindings conforme o usuário assina ou cancela categorias, e consome as mensagens de forma assíncrona. Ao receber uma notícia, exibe o título e o resumo no terminal.

Os clientes rodam no terminal e conversam somente com o broker. Por isso, não existe servidor central entre eles.

## 4. Topologia de tópicos e exchanges

Foi utilizada uma única exchange, chamada `noticias`, do tipo topic. Cada categoria de notícia é uma routing key, e os subscribers recebem apenas as categorias que assinaram.

| Propriedade             | Valor                                                                      |
| ----------------------- | -------------------------------------------------------------------------- |
| Nome                    | `noticias`                                                                 |
| Tipo                    | topic                                                                      |
| Durabilidade            | durável                                                                    |
| auto_delete             | não                                                                        |
| Quem declara a exchange | publisher e subscriber (declarar uma exchange que já existe não gera erro) |

Árvore de categorias (exemplo do enunciado):

```text
noticias
  tecnologia
  esportes
  cultura
```

No enunciado a árvore aparece como noticias/tecnologia. No RabbitMQ, `noticias` é o nome da exchange e a routing key é só a categoria. Por isso, a notícia de tecnologia é publicada na exchange `noticias` com a routing key `tecnologia`. Nesta entrega não há subcategorias, então cada routing key tem uma palavra só.

Routing keys e categorias permitidas:

| Categoria       | Routing key  | Descrição                                        |
| --------------- | ------------ | ------------------------------------------------ |
| tecnologia      | `tecnologia` | Notícias de tecnologia                           |
| esportes        | `esportes`   | Notícias de esportes                             |
| cultura         | `cultura`    | Notícias de cultura                              |
| Tópico de teste | `teste`      | Usado somente na validação da comunicação básica |

Os clientes aceitam essas quatro routing keys. A routing key `teste` existe só para validar a comunicação básica e não é uma categoria de notícia do feed.

Uso de wildcards:

- No topic exchange, o `*` substitui exatamente uma palavra e o `#` substitui zero ou mais palavras.
- O cliente aceita na assinatura o nome exato de uma categoria permitida ou `#`. Qualquer outro padrão é recusado, inclusive `*`.
- Como as routing keys têm uma palavra só, o `#` casa com todas elas, inclusive com `teste`. Portanto, um subscriber com `#` ativo também recebe as mensagens de teste.
- Se a mesma fila tiver `#` e uma categoria (por exemplo, `esportes`), existem dois bindings, mas cada notícia é entregue uma vez só na fila (verificado, seção 10).
- Cancelar uma categoria não adianta se o `#` estiver ativo, porque o `#` continua casando com ela (verificado, seção 10). Para parar de receber uma categoria, é preciso cancelar o `#` e assinar as outras categorias.

## 5. Formato da mensagem

As notícias são enviadas como JSON em UTF-8, no corpo da mensagem, com `content_type` igual a `application/json`. A categoria aparece duas vezes: na routing key (usada pelo broker para entregar) e no campo `categoria` (usado pelo subscriber para exibir e conferir).

| Campo          | Tipo   | Obrigatório | Regra de validação                                                                   |
| -------------- | ------ | ----------- | ------------------------------------------------------------------------------------ |
| `id`           | string | sim         | UUID na forma padrão, com hifens (por exemplo, o gerado por `uuid4`)                 |
| `categoria`    | string | sim         | Deve estar na lista de categorias permitidas e ser igual à routing key               |
| `titulo`       | string | sim         | Não pode ser vazio nem ter só espaços, no máximo 100 caracteres                      |
| `resumo`       | string | sim         | Não pode ser vazio nem ter só espaços, no máximo 300 caracteres                      |
| `publicado_em` | string | sim         | ISO 8601 com data, hora e fuso (`Z` ou `+hh:mm`), por exemplo `2026-11-17T19:30:00Z` |

Exemplo sintético:

```json
{
  "id": "3f2b8c1e-5d4a-4c7e-9b61-0a1d2e3f4a5b",
  "categoria": "tecnologia",
  "titulo": "Exemplo de título da notícia",
  "resumo": "Exemplo de resumo com uma ou duas frases sobre a notícia.",
  "publicado_em": "2026-11-17T19:30:00Z"
}
```

Validações:

- Campos obrigatórios: `id`, `categoria`, `titulo`, `resumo` e `publicado_em`. Se algum faltar, a mensagem é inválida. Não existe campo extra: se uma mensagem trouxer um campo a mais, ele é ignorado.
- Tipos: todos os campos são strings.
- Categorias permitidas: `tecnologia`, `esportes` e `cultura` (mais `teste`, só para a validação da comunicação básica).
- Limites de tamanho: título com até 100 caracteres e resumo com até 300 caracteres.
- Data: `publicado_em` é gerado em UTC, com sufixo `Z`, e o validador também aceita outro fuso no formato `+hh:mm`.
- Id do subscriber: o `--id` aceita letras, dígitos, `-` e `_`, de 1 a 32 caracteres, e é validado antes de conectar. Ele forma o nome da fila (`fila.<id>`).

Onde a validação acontece:

- Publisher: monta e valida a notícia antes de conectar ao broker. Se for inválida, mostra os erros, sai com código 1 e não envia nada. A routing key também precisa ser uma categoria permitida.
- Subscriber: valida cada mensagem recebida. Se o JSON estiver quebrado, faltar campo ou a categoria for diferente da routing key, mostra um aviso no terminal e descarta a mensagem com `basic_nack(requeue=False)`, para ela não ser reentregue em loop. O subscriber continua rodando. Como o projeto não tem dead-letter exchange, a mensagem descartada é perdida.

A validação nos dois lados tem uma razão: o broker não valida o corpo da mensagem, e qualquer cliente com acesso à exchange pode publicar nela, sem usar o publisher do projeto. Além disso, só o subscriber consegue conferir a categoria contra a routing key usada na entrega. Por isso, o publisher evita enviar mensagens inválidas, e o subscriber não confia no que chega.

As regras ficam em `src/mensagem.py`, usado pelos dois lados, e os casos válidos e inválidos estão em `testes/test_mensagem.py`.

## 6. Modelagem do estado central

Não existe servidor de aplicação, por isso o estado fica dividido entre o broker e os clientes. O publisher não guarda estado: ele monta a notícia, valida e envia, sem registro local. Foram utilizadas filas duráveis, para que um subscriber offline não perca as notícias das categorias que já tinha assinado.

| Dado                          | Onde vive                                 | Durável ou volátil | Observação                                                                                                |
| ----------------------------- | ----------------------------------------- | ------------------ | --------------------------------------------------------------------------------------------------------- |
| Exchange `noticias`           | Broker                                    | Durável            | Declarada com `durable=True`, pelo publisher e pelo subscriber                                            |
| Filas                         | Broker                                    | Durável            | Uma por subscriber, chamada `fila.<id>`, com `durable=True`, `exclusive=False` e `auto_delete=False`      |
| Bindings (fila e routing key) | Broker                                    | Durável            | Pertencem à fila e continuam depois que o subscriber encerra                                              |
| Mensagens em trânsito         | Broker, dentro da fila de cada subscriber | Durável            | Publicadas com `DeliveryMode.Persistent`, ficam na fila até o ack do subscriber                           |
| Lista de assinaturas ativas   | Subscriber, em memória                    | Volátil            | Zerada quando o subscriber é reiniciado, e os bindings antigos são removidos na partida (seção 7)         |
| Categorias permitidas         | `src/config.py`                           | Durável            | Fica no código, e a mesma lista é usada pelo publisher e pelo subscriber                                  |
| Parâmetros de conexão         | `src/config.py`                           | Durável            | Credenciais no código, válidas só para ambiente local                                                     |

Quando o subscriber está offline, as mensagens ficam na fila dele e chegam quando ele reconecta com o mesmo id. Isso vale apenas para as categorias que tinham binding no momento da publicação. Os bindings continuam no broker enquanto o subscriber está parado, e só são removidos quando ele inicia de novo (seção 7). Se nenhuma fila tiver binding para a routing key, o broker descarta a mensagem. Depois do ack, a mensagem sai da fila, e o broker não guarda histórico de notícias.

O subscriber usa ack manual (`auto_ack=False`) e `basic_qos(prefetch_count=1)`. Dessa forma, o broker só entrega a próxima mensagem depois do ack da anterior, e uma mensagem não confirmada deve voltar para a fila se a conexão cair (comportamento descrito na documentação do RabbitMQ, não testado).

Se o broker for reiniciado, a exchange, a fila, o binding e a mensagem persistente continuam existindo, porque o `compose.yaml` monta o volume `rabbitmq_data` em `/var/lib/rabbitmq`. Isso foi verificado com `docker compose restart rabbitmq` e uma mensagem (seção 10).

## 7. Assinaturas dinâmicas

Cada subscriber muda os bindings da própria fila diretamente no broker, sem servidor intermediário. A mudança acontece na partida (opção `--assinar`) e, na Entrega 2, também em tempo de execução, pelos comandos descritos abaixo.

Inicialização do subscriber:

1. O usuário informa o `--id` (por exemplo, `sub1`), que é validado.
2. O subscriber declara a exchange `noticias` e a fila `fila.<id>` (durável, não exclusiva e sem `auto_delete`). Se a fila já existe, ela é reaproveitada.
3. O subscriber remove da fila os bindings antigos (os 5 padrões possíveis: `tecnologia`, `esportes`, `cultura`, `teste` e `#`), para iniciar sem nenhuma assinatura. As notícias que já estavam na fila continuam lá e são entregues.
4. A opção `--assinar <padrão>` é um atalho opcional e pode ser repetida. Sem ela, o subscriber inicia sem nenhuma categoria assinada. Cada padrão (categoria permitida ou `#`) vira um binding da fila na exchange. Padrões repetidos são ignorados, e qualquer outro padrão, inclusive `*`, faz o subscriber recusar a execução.
5. O subscriber começa a consumir de forma assíncrona e mostra categoria, título e resumo de cada notícia válida.

Encerrar o subscriber com Ctrl+C ou com o comando `sair` não apaga a fila nem os bindings. Os bindings só são removidos na próxima partida (passo 3).

Fluxo de assinar:

1. O usuário digita o comando de assinar com um padrão (por exemplo, `assinar esportes`).
2. O subscriber confere se o padrão é uma categoria permitida ou `#`, e se ainda não está na lista local.
3. O subscriber cria um binding entre a sua fila e a exchange `noticias`, usando o padrão como routing key.
4. O padrão entra na lista local de assinaturas ativas e o terminal mostra uma confirmação.
5. A partir daí, as notícias que casam com o padrão passam a chegar na fila do subscriber.

Fluxo de cancelar:

1. O usuário digita o comando de cancelar com um padrão (por exemplo, `cancelar esportes`).
2. O subscriber confere se o padrão está na lista local de assinaturas ativas.
3. O subscriber remove o binding da sua fila com a exchange.
4. O padrão sai da lista local e o terminal mostra uma confirmação.
5. As notícias novas deixam de chegar. Mensagens que já estavam na fila antes do cancelamento ainda podem ser entregues.

Comandos do cliente subscriber (um por linha, digitados enquanto as notícias chegam):

| Comando             | Efeito                                                               |
| ------------------- | -------------------------------------------------------------------- |
| `assinar <padrão>`  | Cria o binding e adiciona o padrão à lista                           |
| `cancelar <padrão>` | Remove o binding e tira o padrão da lista                            |
| `listar`            | Mostra as assinaturas ativas no momento                              |
| `sair`              | Encerra o subscriber, mantendo a fila e os bindings no broker        |

Regras do `#`:

- Assinar `#` e uma categoria cria dois bindings na mesma fila, mas a notícia é entregue uma vez só.
- Com `#` ativo, cancelar uma categoria não adianta, porque o `#` continua casando com ela.
- Cancelar o `#` remove só esse binding, e as categorias assinadas separadamente continuam ativas.
- O `#` também casa com a routing key `teste`.

Funcionamento sem servidor central:

- Cada subscriber conversa só com o broker, que é o único ponto em comum do sistema. Não há servidor de aplicação para registrar ou repassar as assinaturas.
- Como cada subscriber tem a própria fila, mudar as assinaturas de um não afeta os outros.
- Se o usuário assinar um padrão inválido, o comando é recusado com uma mensagem de erro. Se o padrão já estiver assinado, o subscriber apenas avisa e não cria outro binding.

Recuperação da lista local ao reconectar com o mesmo id (decisão da Entrega 2):

Como a fila é durável, os bindings continuam no broker quando o subscriber encerra, mas a lista local de assinaturas começa vazia. Para as duas coisas coincidirem, o subscriber remove os bindings antigos da fila na partida (passo 3 da inicialização). Assim, a lista vazia corresponde ao que está no broker, e o comando `listar` mostra o que está realmente ativo. A consequência é que as assinaturas não sobrevivem a um reinício: é preciso assinar de novo, com `assinar` ou `--assinar`.

Duas alternativas foram avaliadas e não foram adotadas, por ficarem além do mínimo pedido (ver seção 12):

- Opção A: consultar a API HTTP de management (`GET /api/queues/%2F/fila.<id>/bindings`) e montar a lista a partir dos bindings da exchange `noticias`. Mantém o broker como única fonte da verdade, mas passa a depender do plugin de management e de uma segunda conexão (HTTP).
- Opção B: guardar a lista em um arquivo local por id. É simples e não depende do management, mas o arquivo pode divergir do broker se os bindings forem alterados por outro meio (por exemplo, pela interface de management).

Concorrência no subscriber:

O subscriber precisa esperar notícias e esperar o usuário digitar ao mesmo tempo, e as duas operações bloqueiam (`start_consuming()` e `input()`). Por isso, cada uma roda em uma thread.

| Thread    | O que faz                                                                                              | Conexão                                                          |
| --------- | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| Consumo   | `basic_consume` e `start_consuming()`. O callback valida, mostra a notícia, faz o ack e registra o log | Uma `BlockingConnection` criada dentro da thread e só usada nela |
| Principal | Lê os comandos com `input()` e mantém a lista local de assinaturas                                     | Uma conexão curta por comando: abre, faz o bind ou unbind, fecha |

Motivos do desenho:

- A conexão do pika não é thread-safe, então uma conexão só é usada pela thread que a criou.
- O binding fica no broker, e não na conexão. Criar o binding por outra conexão tem o mesmo efeito, e a fila passa a receber a categoria na hora, sem a thread de consumo saber.
- Uma conexão parada esperando o `input()` não responde aos heartbeats do broker. A conexão curta por comando evita esse problema.
- A thread de consumo é `daemon`, então termina junto com o programa. Uma notícia recebida e ainda sem ack volta para a fila.
- Uma notícia pode ser impressa enquanto o usuário digita, e a linha fica misturada. Para esta entrega isso é aceitável.

Logs:

Os dois clientes usam `src/logs.py`, que configura o logging do Python com data, nível, nome do cliente e mensagem. Os logs vão para o stderr, e as notícias exibidas ao usuário ficam no stdout. Exemplo:

```text
2026-11-21 12:00:00 INFO publisher.pub1 publicacao id=3f2b8c1e-... categoria=esportes
2026-11-21 12:00:00 INFO subscriber.sub1 entrega id=3f2b8c1e-... categoria=esportes
```

| Evento                               | Quem gera  | O que mostra                                                 |
| ------------------------------------ | ---------- | ------------------------------------------------------------ |
| `conexao`                            | os dois    | estado (conectado, desconectado ou falha), host e porta      |
| `binding_criado`, `binding_removido` | subscriber | fila e padrão                                                |
| `limpeza_bindings`                   | subscriber | fila, na partida (remoção dos bindings antigos)              |
| `publicacao`                         | publisher  | id e categoria da notícia                                    |
| `entrega`                            | subscriber | id e categoria da notícia                                    |
| `descarte`                           | subscriber | routing key e motivo (mensagem inválida)                     |

O id da notícia aparece no log do publisher e no de cada subscriber que a recebeu, então dá para seguir uma notícia do envio até cada entrega. O `publicacao` é registrado depois da confirmação do broker, que não diz se alguma fila recebeu a mensagem. O `entrega` é registrado depois do ack.

## 8. Estrutura de pastas

```text
.
├── .gitignore
├── LICENSE
├── README.md
├── compose.yaml
├── requirements.txt
├── evidencias
│   └── .gitkeep
├── src
│   ├── config.py
│   ├── logs.py
│   ├── mensagem.py
│   ├── publisher.py
│   └── subscriber.py
└── testes
    ├── test_logs.py
    ├── test_mensagem.py
    ├── test_publisher.py
    └── test_subscriber.py
```

| Item                      | Descrição                                                                                                              |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `.gitignore`              | Arquivos ignorados pelo git (template para Python, com entradas para RabbitMQ).                                        |
| `LICENSE`                 | Licença do projeto.                                                                                                    |
| `README.md`               | Documentação da entrega (este arquivo).                                                                                |
| `compose.yaml`            | Sobe o RabbitMQ (imagem `rabbitmq:4-management`) com as portas 5672 e 15672 e o volume `rabbitmq_data`.                |
| `requirements.txt`        | Dependências Python (pika 1.3.2).                                                                                      |
| `src/config.py`           | Parâmetros de conexão (hardcoded, só para ambiente local), nome da exchange, prefixo das filas, categorias e limites.  |
| `src/logs.py`             | Configura o logging (data, nível, nome do cliente e mensagem, no stderr), usado pelos dois clientes.                   |
| `src/mensagem.py`         | Criação e validação da mensagem, do padrão de assinatura e do id do subscriber, usado pelos dois lados.                |
| `src/publisher.py`        | Publisher: valida e publica na exchange `noticias`, uma notícia por execução ou N notícias de exemplo (`--repetir`), com logs. |
| `src/subscriber.py`       | Subscriber: declara a fila `fila.<id>`, consome em uma thread e lê comandos (assinar, cancelar, listar, sair) na principal, com logs. |
| `testes/test_mensagem.py` | Testes unitários (unittest) das validações de `src/mensagem.py`.                                                       |
| `testes/test_logs.py`     | Testes do formato e do destino (stderr) dos logs.                                                                      |
| `testes/test_publisher.py` | Testes dos argumentos do publisher e das notícias de exemplo.                                                          |
| `testes/test_subscriber.py` | Testes dos comandos do subscriber e do tratamento das mensagens recebidas.                                             |
| `evidencias/`             | Logs e capturas de tela da validação com vários clientes (seção 10.2).                                                 |

## 9. Como rodar

Todos os comandos abaixo são executados na raiz do repositório.

Pré-requisitos:

- Docker 29.9.2 e Docker Compose 5.6.1.
- Python 3.14.8 e pip.

Subir o broker:

```bash
docker compose up -d
```

Instalar dependências:

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Rodar o subscriber (um terminal por subscriber). Os bindings antigos da fila são removidos na partida, então o subscriber sempre começa só com o que foi pedido:

```bash
# sem --assinar, o subscriber inicia sem nenhuma categoria assinada
python src/subscriber.py --id sub1

# atalho opcional: assina na partida (pode ser repetido; o # precisa de aspas no shell)
python src/subscriber.py --id sub2 --assinar esportes --assinar cultura
python src/subscriber.py --id sub3 --assinar '#'
```

Comandos do subscriber, digitados um por linha enquanto as notícias chegam:

```text
> assinar esportes
> assinar cultura
> listar
> cancelar esportes
> sair
```

Para testar a mudança de assinaturas: suba o `sub1` sem `--assinar`, publique uma notícia de `esportes` (nada chega), digite `assinar esportes` e publique outra (ela aparece), depois digite `cancelar esportes` e publique mais uma (nada chega). Um padrão inválido (como `futebol` ou `*`) é recusado, e assinar de novo um padrão já assinado só gera um aviso.

Rodar o publisher. Modo de uma notícia por execução (categoria, título e resumo, nessa ordem):

```bash
# publica uma noticia de tecnologia
python src/publisher.py tecnologia "Título da notícia" "Resumo da notícia."

# o --id aparece no nome do logger (publisher.pub1)
python src/publisher.py --id pub1 esportes "Título" "Resumo."
```

Modo repetido, que publica N notícias de exemplo, uma por segundo, em categorias sorteadas (use um terminal por publisher para ter vários ao mesmo tempo):

```bash
python src/publisher.py --id pub1 --repetir 10
python src/publisher.py --id pub2 --repetir 10
```

Logs: os dois clientes escrevem os logs no stderr (conexão, bindings, publicação, entrega e descarte, seção 7), e as notícias exibidas ficam no stdout. Para guardar só os logs em arquivo, redirecione o stderr, por exemplo `2> evidencias/sub1.txt`. A validação com vários clientes está na seção 10.2.

Rodar os testes unitários:

```bash
# roda os testes do validador, dos comandos, dos logs e do publisher
python -m unittest discover -s testes -v
```

Interface de management (portas e credenciais definidas no `compose.yaml`):

- URL: http://localhost:15672
- Usuário: admin
- Senha: admin

A API HTTP respondeu a esse login durante a validação. A tela web não foi aberta (ver seção 10).

Parâmetros de conexão: host `localhost`, porta 5672, usuário `admin` e senha `admin`. Esses valores estão escritos diretamente em `src/config.py`, e valem só para o ambiente local desta disciplina.

Encerrar o ambiente:

```bash
# para e remove os containers, mantendo o volume
docker compose down

# para e remove os containers e o volume (apaga as filas e as mensagens)
docker compose down -v
```

## 10. Validação

### 10.1 Comunicação básica (Entrega 1)

Verificado com Docker 29.9.2, Docker Compose 5.6.1, RabbitMQ 4.4.0 (imagem `rabbitmq:4-management`), Python 3.14.8 e pika 1.3.2. A captura de tela da interface de management ainda está pendente.

O teste usa a routing key `teste`. Um subscriber mínimo (`--id sub1 --assinar teste`) assina essa routing key e um publisher mínimo publica uma mensagem nela. Os terminais foram executados em segundo plano, por isso a saída do subscriber foi lida de um arquivo de log.

Passo a passo:

1. Subir o broker com `docker compose up -d` e conferir o container com `docker compose ps`. Resultado: container `rabbitmq` com status `Up` e as portas 5672 e 15672 publicadas.
2. Rodar os testes unitários com `python -m unittest discover -s testes -v`. Resultado na Entrega 1: 26 testes, todos com `OK`.
3. Iniciar o subscriber mínimo.
4. Publicar uma mensagem de teste com o publisher mínimo.
5. Confirmar que o subscriber mostrou a mensagem no terminal.
6. Publicar uma mensagem com outra routing key (`esportes`) e confirmar que o subscriber não recebe, já que só assinou `teste`.
7. Conferir exchange, fila e binding no broker.

Terminal do subscriber (passos 3 e 5):

```text
Subscriber 'sub1' conectado. Fila: fila.sub1
Assinaturas pedidas: teste
Aguardando notícias (Ctrl+C para sair).
[teste] Mensagem de teste
    Primeira notícia de teste da comunicação com o broker.
```

Terminal do publisher (passo 4, código de saída 0):

```text
Notícia publicada em noticias com routing key 'teste':
{
  "id": "7475532f-e540-4149-b0c0-828a62909d43",
  "categoria": "teste",
  "titulo": "Mensagem de teste",
  "resumo": "Primeira notícia de teste da comunicação com o broker.",
  "publicado_em": "2026-11-17T22:47:21Z"
}
```

Depois da publicação em `esportes` (passo 6), o terminal do subscriber não mostrou nenhuma linha nova.

Estado no broker (passo 7), consultado pela API HTTP de management:

```text
exchange: {'name': 'noticias', 'type': 'topic', 'durable': True, 'auto_delete': False}
fila: {'name': 'fila.sub1', 'durable': True, 'exclusive': False, 'auto_delete': False}
bindings: noticias -> fila.sub1 rk= teste
```

A fila também tem o binding automático da exchange padrão (`(default) -> fila.sub1`), que o RabbitMQ cria para toda fila. Uma mensagem lida da fila sem ser consumida tinha `delivery_mode: 2`, `content_type: application/json` e `routing_key: teste`.

Teste extra (a): subscriber offline recebe ao reconectar com o mesmo id.

1. O subscriber `sub1` foi encerrado com Ctrl+C e mostrou `Encerrando (a fila continua no broker).`
2. Foram publicadas duas mensagens em `teste` com o subscriber parado.
3. O subscriber foi iniciado de novo com `--id sub1`, sem `--assinar`.

```text
Subscriber 'sub1' conectado. Fila: fila.sub1
Nenhuma categoria assinada nesta execução.
Aguardando notícias (Ctrl+C para sair).
[teste] Offline 1
    Primeira mensagem enviada com o subscriber parado.
[teste] Offline 2
    Segunda mensagem enviada com o subscriber parado.
```

### 10.2 Vários publishers e subscribers ao mesmo tempo (Entrega 2)

Objetivo: mostrar que, com vários clientes rodando juntos, cada subscriber recebe só as categorias que assinou, e que assinar e cancelar durante a execução muda o que chega, sem reiniciar o cliente.

Status: o roteiro foi executado contra o RabbitMQ real em 22/11/2026, e os logs e a captura de tela estão em `evidencias/`. Os resultados estão no final desta seção.

Preparação (na raiz do repositório, com o broker no ar e o ambiente virtual ativo):

```bash
docker compose down -v && docker compose up -d   # zera filas e bindings
mkdir -p evidencias
```

Os logs vão para o stderr, então cada terminal usa `2> >(tee ... >&2)` (bash) para mostrar no console e guardar em arquivo. Os arquivos usam a extensão `.txt` porque o `.gitignore` ignora `*.log`. O `#` precisa de aspas na linha de comando, senão o shell o trata como comentário.

Cenário:

| Terminal | Cliente                | Assinaturas iniciais   |
| -------- | ---------------------- | ---------------------- |
| 1        | subscriber `sub1`      | `esportes`             |
| 2        | subscriber `sub2`      | `tecnologia`, `cultura` |
| 3        | subscriber `sub3`      | `#`                    |
| 4        | publisher `pub1`       | (publica 20 notícias)  |
| 5        | publisher `pub2`       | (publica 20 notícias)  |

Passos:

1. Subir os três subscribers, um em cada terminal:

```bash
# terminal 1
python src/subscriber.py --id sub1 --assinar esportes 2> >(tee evidencias/sub1.txt >&2)

# terminal 2
python src/subscriber.py --id sub2 --assinar tecnologia --assinar cultura 2> >(tee evidencias/sub2.txt >&2)

# terminal 3
python src/subscriber.py --id sub3 --assinar '#' 2> >(tee evidencias/sub3.txt >&2)
```

2. Rodada 1: subir os dois publishers quase juntos (cada um publica 10 notícias, uma por segundo) e esperar que terminem:

```bash
# terminal 4
python src/publisher.py --id pub1 --repetir 10 2> >(tee evidencias/pub1.txt >&2)

# terminal 5
python src/publisher.py --id pub2 --repetir 10 2> >(tee evidencias/pub2.txt >&2)
```

3. Com os publishers parados, digitar nos subscribers:

```text
# terminal 1 (sub1)
> assinar cultura
> listar

# terminal 2 (sub2)
> cancelar cultura
> listar
```

4. Rodada 2: subir os publishers de novo, acrescentando ao mesmo arquivo de log (`tee -a`):

```bash
# terminal 4
python src/publisher.py --id pub1 --repetir 10 2> >(tee -a evidencias/pub1.txt >&2)

# terminal 5
python src/publisher.py --id pub2 --repetir 10 2> >(tee -a evidencias/pub2.txt >&2)
```

5. Esperar os publishers terminarem e digitar `listar` e `sair` em cada subscriber.

Resultado esperado:

| Cliente | Antes do comando                 | Depois do comando                                                          |
| ------- | -------------------------------- | -------------------------------------------------------------------------- |
| `sub1`  | só `esportes`                    | `esportes` e `cultura` (cultura só a partir do `binding_criado`)           |
| `sub2`  | `tecnologia` e `cultura`         | só `tecnologia` (nenhuma cultura nova depois do `binding_removido`)        |
| `sub3`  | todas as categorias              | todas as categorias, sem mudança                                           |

Observação: mensagens que já estavam na fila (ou já entregues ao cliente com prefetch 1) quando o comando foi dado ainda podem chegar logo depois do `cancelar`, como descrito na seção 7. Essas entregas devem ser comparadas com o horário do `binding_removido`.

Execução realizada (22/11/2026, com o broker zerado por `docker compose down -v`): foram iniciados os três subscribers e rodadas duas vezes os dois publishers, com 10 notícias cada (`--repetir 10`). As assinaturas foram alteradas entre as rodadas, com os publishers parados, para que os comandos não se misturassem com as notícias que chegam.

| Etapa                                         | Horário (19:2x)     |
| --------------------------------------------- | ------------------- |
| Rodada 1 (pub1 e pub2)                        | 19:26:17 a 19:26:27 |
| `assinar cultura` no sub1 (binding_criado)    | 19:27:06            |
| `cancelar cultura` no sub2 (binding_removido) | 19:27:19            |
| Rodada 2 (pub1 e pub2)                        | 19:28:01 a 19:28:11 |

Entregas por rodada (conferidas comparando o id de cada notícia publicada com as entregas de cada subscriber):

| Cliente | Rodada 1 (antes dos comandos)                 | Rodada 2 (depois dos comandos)                |
| ------- | --------------------------------------------- | --------------------------------------------- |
| `sub1`  | 6 de esportes                                 | 6 de esportes e 7 de cultura                  |
| `sub2`  | 8 de tecnologia e 6 de cultura                | 7 de tecnologia                               |
| `sub3`  | 8 de tecnologia, 6 de esportes e 6 de cultura | 7 de tecnologia, 6 de esportes e 7 de cultura |

Resultado obtido:

| Item                                                       | Resultado                                                                                                    |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Total de notícias publicadas por `pub1` e `pub2`           | 40 (20 de cada): 15 de tecnologia, 13 de cultura e 12 de esportes                                            |
| Entregas de `sub1` por categoria                           | 19: 12 de esportes e 7 de cultura                                                                            |
| Entregas de `sub2` por categoria                           | 21: 15 de tecnologia e 6 de cultura                                                                          |
| Entregas de `sub3` por categoria                           | 40: 15 de tecnologia, 13 de cultura e 12 de esportes                                                         |
| Nenhuma entrega fora das categorias assinadas              | Confirmado. Não houve entrega extra nem entrega faltando em nenhum subscriber                                |
| Efeito do `assinar cultura` em `sub1`                      | As 6 notícias de cultura da rodada 1 não chegaram. As 7 da rodada 2 chegaram                                 |
| Efeito do `cancelar cultura` em `sub2`                     | As 6 de cultura da rodada 1 chegaram (a última às 19:26:25). As 7 da rodada 2 não chegaram                   |
| Captura de tela da interface de management (`evidencias/`) | `rabbitmq_bindings.png`: `fila.sub1` com esportes e cultura, `fila.sub2` com tecnologia, `fila.sub3` com `#` |

Exemplos de notícia seguida pelo id:

- `6890bdf2-42bd-41ca-854e-df2896e50040` (cultura, rodada 1, publicada pelo `pub1` às 19:26:20): entregue ao `sub2` e ao `sub3`, e não ao `sub1`, que ainda não assinava cultura.
- `3574502f-c2bf-4d9f-a191-09c54fff1111` (cultura, rodada 2, publicada pelo `pub1` às 19:28:01): entregue ao `sub1` e ao `sub3`, e não ao `sub2`, que já tinha cancelado cultura.

Limite da validação: os comandos foram dados com os publishers parados. Por isso, o caso de uma notícia que já estava na fila no momento do `cancelar` (seção 7) não foi exercitado.

Observação sobre os arquivos: alguns `>` aparecem no início de linhas dos logs dos subscribers. Eles são o prompt do `input()` e não afetam as linhas de log.

Evidências: `evidencias/pub1.txt`, `pub2.txt`, `sub1.txt`, `sub2.txt`, `sub3.txt` e `evidencias/rabbitmq_bindings.png`.

## 11. Status

Implementado na Entrega 2:

- Subscriber interativo: `assinar`, `cancelar`, `listar` e `sair`, com consumo e comandos ao mesmo tempo (seção 7).
- Remoção dos bindings antigos na partida do subscriber, no lugar das opções A e B.
- Logs de conexão, binding, publicação, entrega e descarte nos dois clientes (seção 7).
- Publisher com `--id` e modo repetido (`--repetir N`), mantendo o modo de uma notícia por execução.
- Testes unitários dos comandos, dos logs e dos argumentos do publisher, além dos 26 testes do validador (56 no total).

Pendente:

- Executar o roteiro da seção 10.2 com o broker real, guardar os logs em `evidencias/` e preencher a tabela de resultados.
- Tirar a captura de tela da interface de management.
- Registrar a evidência do teste extra (b), do reinício do broker, citado na seção 6, e a verificação do comportamento do `#` citada na seção 4. Os dois estavam citados no texto, mas o resultado não está documentado na seção 10.1.
- Confirmar com o professor se vários processos do publisher em terminais separados contam como múltiplos publishers simultâneos.
- Conferir no primeiro teste real que o RabbitMQ aceita remover um binding que não existe, sem erro (a limpeza da partida depende disso).

## 12. Próximos passos

Itens que não foram pedidos no enunciado e ficaram de fora para manter o trabalho no mínimo:

- Recuperar as assinaturas de uma execução anterior (opções A e B da seção 7).
- Encerrar o consumo de forma organizada, com `add_callback_threadsafe`.
- Detectar a queda do broker e reconectar.
- Script automático de teste com vários clientes.
- Evitar que uma notícia impressa se misture com a linha que o usuário está digitando.

## 13. Referências

- RabbitMQ, tutorial 5 (Topics), em Python: https://www.rabbitmq.com/tutorials/tutorial-five-python
- RabbitMQ, documentação de exchanges, filas, confirmações do publisher e acks do consumidor: https://www.rabbitmq.com/docs
- pika, documentação: https://pika.readthedocs.io/
- Python, módulo `threading`: https://docs.python.org/3/library/threading.html
- Python, módulo `logging`: https://docs.python.org/3/library/logging.html
- Python, módulo `unittest`: https://docs.python.org/3/library/unittest.html
