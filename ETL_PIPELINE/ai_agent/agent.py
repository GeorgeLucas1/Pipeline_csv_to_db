from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from agno.agent import Agent
from agno.models.groq import Groq
from agno.team import Team
from skills import ler_dados_anomalos, ler_dados_processados, salvar_insight
#é necessario falar  modelo caso nao tenha ele buscara pela openai
# --- AGENTE DE ANOMALIAS ---
agente_anomalias = Agent(
    name="DOUTOR ANOMALIAS",
    model=Groq(id="llama-3.3-70b-versatile"),
    description=(
        "Voce e responsavel por analisar registros que falharam na validacao "
        "do pipeline ETL. Cada registro anomalo possui campos como batch_id, "
        "record_id, source_file, source_table, rule_code (ex: BUSINESS_001, "
        "TYPE_001, DOMAIN_001), severity, observed_value, expected_value e "
        "recommended_action. Seu papel e interpretar esses metadados e "
        "fornecer uma explicacao tecnica clara de cada problema encontrado."
    ),
    instructions=[
        "Chame 'ler_dados_anomalos' SEMPRE como primeiro passo para obter os registros em quarentena.",
        "Para CADA registro anomalo identificado, responda com:",
        "  - rule_code: qual regra foi violada",
        "  - source_table: de qual tabela Silver veio o registro",
        "  - severity: severidade (critical, error ou warning)",
        "  - motivo: explicacao tecnica clara em 1-2 frases",
        "  - acao_recomendada: Corrigir, Revisar, Aceitar com alerta ou Rejeitar",
        "Agrupe os registros por rule_code e indique quais regras apresentam mais falhas.",
        "Classifique o problema como 'Erro de Origem', 'Inconsistencia de Dados' ou 'Regra de Negocio Violada'.",
        "Depois da analise, salve um insight consolidado com 'salvar_insight' passando a categoria, a observacao e o nome da tabela de origem (tabela_origem).",
        "Nao invente dados. Trabalhe exclusivamente com os dados retornados pela tool.",
        "Se o banco de anomalias nao existir, informe que nao ha dados para analisar."
    ],
    tools=[ler_dados_anomalos, salvar_insight],
    markdown=True
)

agente_insights = Agent(
    name="COPY_THIEF_INSIGHTS",
    model=Groq(id="llama-3.3-70b-versatile"),
    description=(
        "Voce e responsavel por gerar analises de negocio a partir dos dados "
        "aprovados no banco processado. Identifica padroes, tendencias, "
        "distribuicoes e indicadores relevantes. Sua analise deve ser baseada "
        "exclusivamente nos dados reais retornados pelas tools."
    ),
    instructions=[
        "Chame 'ler_dados_processados' informando o nome da tabela como parametro.",
        "Analise os dados retornados e identifique:",
        "  - Distribuicao de valores por coluna categorica",
        "  - Tendencias temporais (se houver coluna de data)",
        "  - Registros com valores fora do esperado ou incomuns",
        "  - Metricas resumidas: contagem total, valores unicos, nulos",
        "Gere um insight em linguagem natural com titulo, descricao e dados de suporte.",
        "Classifique o insight como 'Oportunidade', 'Risco Identificado' ou 'Resumo Executivo'.",
        "Salve o resultado com 'salvar_insight' passando a categoria, a observacao e o nome da tabela de origem (tabela_origem).",
        "Nao faca suposicoes. Trabalhe apenas com os dados retornados.",
        "Se a tabela nao existir, informe o nome das tabelas disponiveis."
    ],
    tools=[ler_dados_processados, salvar_insight],
    markdown=True
)
#MEMBERS ÉÉ A FORMA DE DEFINIR OS AGENTES QUE FAZEM PARTE DO TIME. CADA AGENTE TEM SUAS INSTRUCOES E TOOLS ESPECIFICAS, MAS O TIME COORDENA A ANALISE GERAL.
time_analise = Team(
    name=" ANISADOR DE ANOMALIAS E INSIGHTS",
    model=Groq(id="llama-3.3-70b-versatile"),
    members=[agente_anomalias, agente_insights],
    description="Time que analisa anomalias e gera insights de negocio a partir dos dados do pipeline.",
    instructions=[
        "Analise primeiro as anomalias no banco de erros para entender a saude dos dados.",
        "Depois, gere insights sobre a tabela indicada no banco processado.",
        "Cada agente deve chamar suas tools antes de gerar qualquer resposta.",
        "Os insights devem sempre referenciar a tabela de origem dos dados.",
        "Nao gere analises genericas. Cada resposta deve ser fundamentada nos dados reais."
    ],
    show_members_responses=True
)

if __name__ == "__main__":
    time_analise.print_response(
        "Analise as anomalias no banco de erros e gere insights sobre a tabela 'dataset' no banco processado."
    )
