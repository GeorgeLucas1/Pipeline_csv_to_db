import os
from pathlib import Path

from agno.agent import Agent
from agno.models.groq import Groq
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def testar_conexao():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key.strip() in ("", "coloca sua key no groq console aq"):
        print("ERRO: GROQ_API_KEY nao configurada no arquivo .env")
        return False

    agente = Agent(
        name="Teste de Conexao",
        model=Groq(id="llama-3.3-70b-versatile"),
    )

    try:
        agente.print_response("Responda apenas: conexao ok", markdown=False)
        print("CONEXAO FUNCIONANDO")
        return True
    except Exception as e:  # noqa: BLE001 - teste de conexao deve capturar qualquer erro
        print(f"ERRO NA CONEXAO: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    testar_conexao()
