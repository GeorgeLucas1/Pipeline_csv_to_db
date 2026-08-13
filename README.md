# Data Quality & Insight Platform

## Plataforma de ingestão, qualidade e análise inteligente de dados

Este projeto começou como um pipeline de arquivos CSV e Excel para SQLite. A nova proposta amplia seu objetivo: transformar o pipeline em uma **plataforma local de qualidade e inteligência de dados**, capaz de receber arquivos, limpar e validar registros, identificar anomalias, persistir dados aprovados e relatórios em PostgreSQL executado via Docker e entregar insights analíticos no Streamlit.

O fluxo continua baseado na arquitetura **Medalhão — Bronze, Silver e Gold** —, mas agora possui dois agentes principais e um componente especializado de qualidade:

| Componente | Responsabilidade |
| --- | --- |
| **Agente de Limpeza e Qualidade** | Padroniza colunas, corrige problemas determinísticos, valida tipos, aplica regras de qualidade e encaminha registros problemáticos para a quarentena. |
| **Agente de Anomalias** | Analisa registros suspeitos, explica as regras violadas, informa a tabela de origem e produz uma versão rastreável dos dados anômalos para revisão ou reprocessamento. |
| **Agente de Análise e Insights** | Consulta o banco final, identifica padrões, tendências, indicadores e possíveis explicações, apresentando os resultados no Streamlit. |

> O agente de qualidade decide sobre a qualidade do dado. O agente de insights interpreta dados aprovados. Essa separação evita que dados suspeitos sejam usados como base para conclusões analíticas sem transparência.

## Objetivo do projeto

O objetivo não é apenas converter arquivos em tabelas. O objetivo é persistir o histórico operacional, os dados aprovados e os resultados analíticos em uma base consultável. O objetivo é criar um ciclo completo:

> **Receber → preservar → limpar → validar → separar anomalias → publicar dados aprovados → analisar → explicar insights.**

A plataforma deve responder a três perguntas fundamentais:

1. **O dado recebido pode ser utilizado?**
2. **Quais registros apresentam problemas e em qual tabela deveriam estar?**
3. **O que os dados aprovados indicam sobre o negócio?**

## Arquitetura geral

```mermaid
graph TD
    U[Usuário] --> ST[Streamlit]
    ST --> IN[Ingestão CSV / XLS / XLSX]
    IN --> B[Bronze: arquivo original]

    B --> P[Perfil do arquivo e contrato do schema]
    P --> L[Agente de Limpeza e Qualidade]
    L --> S[Silver: dados normalizados]
    L --> Q[Quarentena de anomalias]

    Q --> A[Agente de Anomalias]
    A --> R[Relatório de anomalias<br/>versão anomalizada + tabela indicada]
    R --> ST

    S --> G[Gold: dados aprovados]
    G --> DB[(PostgreSQL: dados Gold, qualidade e insights)]

    DB --> I[Agente de Análise e Insights]
    I --> INS[Insights, métricas e recomendações]
    INS --> ST

    Q -. correção/revisão .-> B
```

## Camadas de dados

| Camada | Objetivo | Pode ser consumida pelo agente de insights? |
| --- | --- | --- |
| **Bronze** | Preservar o arquivo exatamente como recebido, incluindo dados misturados, nulos e possíveis erros. | Não. Serve como fonte de auditoria e reprocessamento. |
| **Silver** | Normalizar nomes, formatos e tipos; registrar o resultado das regras de qualidade sem esconder a origem dos problemas. | Apenas para análises de qualidade, não para indicadores oficiais. |
| **Quarentena** | Armazenar registros anômalos, motivos, regras violadas, severidade, lote e status de tratamento. | Não por padrão. Pode ser consultada em uma tela específica de qualidade. |
| **Gold** | Conter somente dados aprovados ou explicitamente aceitos com alerta, prontos para consumo analítico. | Sim. É a fonte oficial do agente de insights e fica persistida no PostgreSQL. |

O fato de um arquivo conter colunas ou registros misturados não é um problema da Bronze. A Bronze deve preservar o original. A classificação ocorre durante a transformação para Silver, e a decisão de publicação ocorre antes do Gold.

## Agente de Limpeza e Qualidade

O Agente de Limpeza e Qualidade é responsável pelas regras determinísticas e reproduzíveis. Ele não deve depender exclusivamente de texto gerado por um modelo de linguagem para aprovar ou rejeitar dados.

Suas tarefas incluem padronizar nomes de colunas, remover espaços indevidos, converter tipos, identificar nulos, validar domínios permitidos, conferir chaves, verificar duplicidades e aplicar regras de consistência de negócio. Cada ocorrência deve gerar um registro estruturado com código da regra, severidade, coluna, linha, valor observado e recomendação.

Exemplos de regras para o domínio de compras:

| Código | Regra | Severidade inicial |
| --- | --- | --- |
| `STRUCT_001` | As colunas obrigatórias existem. | Crítica |
| `TYPE_001` | Quantidade, preço, desconto e valor total são numéricos. | Crítica |
| `BUSINESS_001` | O valor total é compatível com quantidade, preço e desconto. | Crítica |
| `BUSINESS_002` | A quantidade é maior que zero. | Crítica |
| `BUSINESS_003` | O desconto está entre 0 e 100. | Crítica |
| `DOMAIN_001` | Canal, pagamento e indicadores possuem valores permitidos. | Erro |
| `DUP_001` | O identificador da compra não se repete no mesmo lote. | Crítica |
| `BUSINESS_004` | Relações entre idade e tempo de cliente são avaliadas. | Alerta |

O agente deve separar **erro**, **alerta** e **anomalia exploratória**. Uma combinação incomum não deve ser automaticamente excluída sem uma regra de negócio que justifique a rejeição.

## Agente de Anomalias

O Agente de Anomalias recebe os registros enviados para a quarentena e produz uma visão compreensível do problema. A saída esperada não é apenas uma mensagem genérica como “linha inválida”. Ela deve indicar:

| Informação | Exemplo |
| --- | --- |
| `batch_id` | `2026-08-12-001` |
| `record_id` | `linha_000127` |
| `source_file` | `vendas_agosto.csv` |
| `source_table` | `fato_compras` |
| `rule_code` | `BUSINESS_001` |
| `severity` | `critical`, `error` ou `warning` |
| `observed_value` | Valor total encontrado no arquivo |
| `expected_value` | Valor calculado pela regra |
| `recommended_action` | Corrigir, revisar, aceitar com alerta ou rejeitar |
| `anomaly_table` | Nome da tabela de quarentena onde o registro foi gravado |

A “versão anomalizada” deve ser entendida como uma **versão dos dados que preserva os registros problemáticos e adiciona metadados de qualidade**. Ela não deve substituir a Bronze, a Silver aprovada ou o Gold.

O agente pode gerar explicações em linguagem natural, mas sua decisão deve permanecer vinculada às regras estruturadas. Correções automáticas só devem ocorrer quando forem determinísticas, como remover espaços extras ou normalizar um separador decimal conhecido.

## Banco final e tabelas de qualidade

A proposta mantém um **PostgreSQL como banco persistente central**, executado localmente por Docker, para dados Gold, qualidade, anomalias, execuções e insights. Os arquivos Bronze, Silver e a Quarentena podem continuar no sistema de arquivos para preservar o histórico bruto e facilitar depuração, mas os resultados operacionais e analíticos devem ser persistidos no PostgreSQL.

| Banco ou tabela | Conteúdo |
| --- | --- |
| PostgreSQL / schema `gold` | Dados aprovados e tipados para consumo analítico. |
| PostgreSQL / schema `quality` | Registros em quarentena, achados, severidade e status de tratamento. |
| `pipeline_runs` | Histórico dos lotes e estados de processamento. |
| `quality_findings` | Uma ocorrência por regra violada, com severidade e status. |
| `anomaly_reports` | Resumos produzidos pelo Agente de Anomalias. |
| PostgreSQL / banco `insights` / tabela `insight_reports` | Insights gerados a partir do Gold, identificando a tabela analisada, a pergunta, a consulta, as métricas, a resposta, o escopo, a data e a versão do agente. |

Cada registro deve possuir `batch_id` e `record_id`. Isso permite responder de onde o dado veio, qual regra falhou, quem analisou o problema, se ele foi corrigido e se foi reprocessado.

## Agente de Análise e Insights

O Agente de Análise e Insights consulta somente o schema `gold` do banco principal por padrão. Ele pode calcular métricas, comparar períodos, encontrar tendências, destacar mudanças relevantes e sugerir perguntas para investigação. Depois de produzir uma resposta, o agente deve salvar o resultado no banco PostgreSQL chamado `insights`, permitindo consultar o histórico de análises no Streamlit.

A interface Streamlit deve apresentar os insights com transparência. Cada resposta precisa informar a tabela consultada no PostgreSQL, as colunas utilizadas, o período analisado, as métricas calculadas e, quando possível, uma visualização ou tabela de apoio. O texto, a consulta executada, os filtros e os resultados resumidos devem ser persistidos na tabela `insight_reports` do banco `insights`.

O agente não deve inventar métricas nem consultar tabelas de quarentena silenciosamente. Caso o usuário queira analisar anomalias, isso deve ocorrer em uma seção explícita de **Qualidade e Anomalias**, separada da seção de **Insights do negócio**.

Exemplos de entregas no Streamlit:

| Área da interface | Entrega |
| --- | --- |
| **Ingestão** | Upload, prévia e identificação do lote. |
| **Qualidade** | Percentual de linhas aprovadas, alertas, rejeições e principais regras violadas. |
| **Anomalias** | Tabela indicada, registros anomalizados, motivo e recomendação. |
| **Dados aprovados** | Consulta às tabelas Gold e indicadores básicos. |
| **Insights** | Pergunta em linguagem natural, resposta explicada, métricas e gráficos. |
| **Histórico** | Execuções, versões, reprocessamentos e relatórios anteriores. |

## Fluxo recomendado no Streamlit

O Streamlit deixa de ser apenas uma tela de upload e passa a ser o centro de operação da plataforma.

```mermaid
sequenceDiagram
    participant U as Usuário
    participant S as Streamlit
    participant L as Agente de Limpeza
    participant Q as Quarentena
    participant A as Agente de Anomalias
    participant DB as Banco Gold
    participant I as Agente de Insights

    U->>S: Envia arquivo
    S->>L: Inicia lote e valida schema
    L->>Q: Registra linhas anômalas
    L->>DB: Publica dados aprovados
    L-->>S: Retorna relatório de qualidade
    S->>A: Solicita análise das anomalias
    A-->>S: Retorna motivos, tabela e recomendações
    U->>S: Faz pergunta analítica
    S->>I: Consulta o banco Gold
    I->>DB: Executa análise autorizada
    DB-->>I: Retorna dados agregados
    I-->>S: Entrega insight fundamentado
```

## Mudança de posicionamento

O nome e a descrição do projeto devem deixar de enfatizar apenas “CSV para DB”. A nova descrição recomendada é:

> **Plataforma local de qualidade e análise inteligente de dados que ingere arquivos tabulares, preserva a origem, normaliza registros, identifica anomalias, publica dados aprovados em PostgreSQL executado via Docker e entrega insights analíticos persistidos e visualizados pelo Streamlit.**

O projeto ainda é um pipeline de dados, mas agora possui valor de portfólio em três áreas: engenharia de dados, qualidade de dados e análise assistida por agente.

## Limites importantes da proposta

A proposta é forte, mas deve ser implementada com uma separação clara entre automação confiável e geração probabilística. O agente de limpeza deve começar com funções e regras testáveis. O agente de anomalias pode usar inteligência artificial para explicar e priorizar achados, desde que não altere dados sem rastreabilidade. O agente de insights deve gerar respostas baseadas em consultas, métricas e tabelas reais do banco.

Não é recomendável começar com três agentes autônomos conversando livremente. Para a primeira versão, prefira um orquestrador simples que execute etapas com contratos definidos: limpeza produz dados e findings; anomalias produz relatório; análise produz insights citando a origem.

## Estrutura proposta do projeto

```text
ETL_PIPELINE/
├── agents/
│   ├── cleaning_agent.py
│   ├── anomaly_agent.py
│   ├── insight_agent.py
│   └── orchestrator.py
├── quality/
│   ├── rules.py
│   ├── schemas.py
│   ├── quarantine.py
│   └── reports.py
├── docker-compose.yml
├── medallion/
│   ├── bronze/
│   ├── silver/
│   ├── quarantine/
│   └── gold/
│       └── database/
├── eda/
│   └── .eda_ETl.py
└── streamlit/
    └── app.py
```

A estrutura acima é uma direção arquitetural. A implementação pode ser incremental, sem exigir a criação de todos os agentes na primeira etapa.

## Roadmap de implementação

| Fase | Entrega |
| --- | --- |
| **Fase 1** | Corrigir o modelo de qualidade: `batch_id`, `record_id`, códigos de regra, severidade e status. |
| **Fase 2** | Criar a tela Streamlit de qualidade e anomalias. |
| **Fase 3** | Implementar o Agente de Anomalias como gerador de explicações e recomendações. |
| **Fase 4** | Criar o Agente de Insights para consultas e métricas do Gold. |
| **Fase 5** | Adicionar histórico de relatórios, reprocessamento e avaliação da qualidade das respostas. |

## Persistência PostgreSQL via Docker

A camada Gold possui dois destinos lógicos: o banco principal, que guarda as tabelas Gold aprovadas, e o banco PostgreSQL `insights`, que guarda o nome da tabela analisada e os resultados produzidos pelo agente de análise.

O PostgreSQL é o servidor persistente principal da plataforma e é executado via Docker. Dentro desse servidor, a plataforma utiliza um banco principal para os dados Gold, qualidade e metadados, além de um banco separado chamado `insights`. O banco `insights` armazena os resultados das análises, incluindo obrigatoriamente o nome da tabela Gold analisada e os insights coletados. O SQLAlchemy realiza as conexões entre o pipeline, o banco Gold e o banco `insights`. A configuração Docker já está documentada e disponível em `docker-compose.yml`; a migração completa das funções atuais de SQLite para PostgreSQL é uma etapa de implementação do roadmap.

A separação lógica recomendada combina schemas no banco principal com um banco separado chamado `insights`:

| Estrutura | Responsabilidade |
| --- | --- |
| `gold` | Tabelas aprovadas para consumo analítico. |
| `quality` | Execuções, regras, findings, quarentena e decisões dos agentes. |
| banco `insights` | Perguntas, nome da tabela analisada, consultas, métricas, respostas e histórico de insights. |
| `metadata` | Lotes, arquivos, hashes, versões de schema e auditoria. |

A tabela principal do banco `insights` deve possuir, no mínimo, a seguinte estrutura conceitual:

| Campo | Conteúdo |
| --- | --- |
| `insight_id` | Identificador único do insight. |
| `source_table` | Nome da tabela Gold analisada. |
| `source_database` | Banco ou conexão de origem dos dados analisados. |
| `question` | Pergunta ou objetivo da análise. |
| `insight_text` | Insight gerado em linguagem natural. |
| `metrics_json` | Métricas e valores que sustentam o insight. |
| `query_text` | Consulta ou plano de consulta utilizado, quando aplicável. |
| `filters_json` | Filtros e período considerados. |
| `created_at` | Data e hora da geração. |
| `agent_version` | Versão do agente responsável pela análise. |

Assim, para cada análise, o Streamlit consegue exibir **qual tabela foi analisada, quais filtros foram usados, quais métricas foram encontradas e qual insight foi produzido**.

O fluxo de persistência é: **arquivo Bronze → transformação e validação → banco principal com Gold e Quality → Agente de Insights → banco PostgreSQL `insights` → Streamlit**. O Streamlit lê os relatórios persistidos; ele não deve ser o local definitivo de armazenamento das respostas.

## Como executar

### Instalação

```bash
pip install -r requirements.txt
```

### Subir o PostgreSQL com Docker

```bash
docker compose up -d postgres
```

O arquivo `docker-compose.yml` incluído neste projeto sobe o serviço `postgres` com volume persistente. A configuração usa variáveis de ambiente, como `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT` e `DATABASE_URL`. O arquivo `.env` não deve ser versionado. Os valores padrão do Compose são apenas para desenvolvimento local.

### Verificar o PostgreSQL

```bash
docker compose ps
docker compose logs postgres
```

### Interface Streamlit

```bash
streamlit run ETL_PIPELINE/streamlit/app.py
```

### Execução do pipeline

```bash
python ETL_PIPELINE/eda/.eda_ETl.py
```

## Estado atual e próximos passos

A implementação atual realiza ingestão, transformação Silver, tipagem Gold, carga local e armazenamento básico de anomalias. A evolução arquitetural proposta substitui o SQLite como persistência principal por PostgreSQL via Docker e acrescenta a persistência dos relatórios de qualidade e insights. A interface Streamlit ainda está centrada no upload e na confirmação do nome da tabela. O próximo passo prioritário é transformar o retorno do pipeline em um relatório estruturado de qualidade e disponibilizá-lo na interface.

Depois disso, o Agente de Anomalias pode explicar os achados e indicar a tabela de quarentena. Somente após o banco Gold estar estável e consultável deve ser implementado o Agente de Insights.

