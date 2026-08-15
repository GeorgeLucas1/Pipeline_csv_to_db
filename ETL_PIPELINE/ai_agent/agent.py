from agno.agent import Agent
from agno.models.groq import Groq
from skills import ler_dados_anomalos, ler_dados_processados, salvar_insight

# --- AGENTE DE ANOMALIAS (Focado no banco de erros) ---
agente_anomalias = Agent(
    name="Detetive de Anomalias",
    model=Groq(id="llama-3.3-70b-versatile"),
    description="Você analisa dados que falharam no pipeline.",
    instructions=[
        "Use 'ler_dados_anomalos' para entender o que deu errado.",
        "Explique de forma técnica por que os dados foram rejeitados.",
        "Salve um insight categorizado como 'Erro de Origem' com a explicação do problema."
    ],
    tools=[ler_dados_anomalos, salvar_insight],
    markdown=True
)

# --- AGENTE DE INSIGHTS (Focado no banco de produção) ---
agente_insights = Agent(
    name="Analista de Negócios",
    model=Groq(id="llama-3.3-70b-versatile"),
    description="Você gera valor a partir dos dados limpos.",
    instructions=[
        "Use 'ler_dados_processados' para analisar a tabela informada.",
        "Identifique tendências, padrões ou curiosidades nos dados.",
        "Salve um insight categorizado como 'Oportunidade' ou 'Resumo'."
    ],
    tools=[ler_dados_processados, salvar_insight],
    markdown=True
)

# --- TIME DE IA ---
time_analise = Agent(
    team=[agente_anomalias, agente_insights],
    instructions=["Coordenem a análise completa dos bancos de dados e garantam que os insights sejam salvos."],
    show_tool_calls=True
)

if __name__ == "__main__":
    # Comando que ativa os dois agentes
    time_analise.print_response(
        "Analise as anomalias no banco de erros e gere insights sobre a tabela 'vendas' no banco processado."
    )
