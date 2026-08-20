import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent
import skills

LOG_DIR = Path(__file__).resolve().parent.parent / "medallion" / "logs"
LOG_FILE = LOG_DIR / "execucoes.log"


def _log(mensagem: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    linha = f"[{datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}] {mensagem}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linha)
    print(linha.strip())


def _validar_insights_antes_de_salvar() -> int:
    if not skills.DB_INSIGHTS.exists():
        return 0
    conn = sqlite3.connect(skills.DB_INSIGHTS)
    total = conn.execute("SELECT COUNT(*) FROM insights").fetchone()[0]
    conn.close()
    return total


def executar(pergunta: str) -> None:
    _log(f"INICIO | Pergunta: {pergunta}")
    _log(f"SEGURANCA | Categorias permitidas: {skills.CATEGORIAS_PERMITIDAS}")

    if skills._detectar_injecao(pergunta):
        _log("BLOQUEADO | Injeção de prompt detectada na pergunta do usuario")
        print("BLOQUEADO: mensagem do usuario contem padrao suspeito.")
        return

    insights_antes = _validar_insights_antes_de_salvar()

    inicio = time.time()
    agent.time_analise.print_response(pergunta)
    duracao = round(time.time() - inicio, 1)

    insights_depois = _validar_insights_antes_de_salvar()
    novos = insights_depois - insights_antes

    _log(f"FIM | Duracao: {duracao}s | Novos insights: {novos}")

    if novos == 0:
        _log("AVISO | Nenhum insight novo foi salvo")
    elif novos > 3:
        _log(f"ALERTA | {novos} insights salvos de uma vez — possivel problema")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        pergunta = " ".join(sys.argv[1:])
    else:
        pergunta = input("Digite sua pergunta: ").strip()

    if not pergunta:
        pergunta = (
            "Analise as anomalias no banco de erros e gere insights "
            "sobre a tabela 'dataset' no banco processado."
        )
        print(f"(usando pergunta padrao)\n{pergunta}\n")

    executar(pergunta)
