"""Avaliação completa da solução de IA -> gera docs/RESULTADOS.md.

Mede: (1) classificador de risco (holdout + validação cruzada), (2) cenários clínicos de referência,
(3) qualidade da recuperação RAG (hit@1 / hit@3), (4) guardrails e (5) pipeline ponta a ponta
(latência e conteúdo dos alertas). Com --with-llm, também roda o cenário crítico com o Gemini.

Uso:  python ai/evaluate.py [--with-llm]
"""
import argparse
import sys
import tempfile
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import guardrails  # noqa: E402
from app.services.knowledge_base import KnowledgeBase  # noqa: E402
from app.services.risk_model import RiskModel, train_and_save  # noqa: E402

CLINICAL_CASES = [
    # (descrição, pet, leitura, esperado)
    ("Cão D4 pós-osteossíntese, sinais normais", ("canino", 4, True, 4), (38.5, 95, "REPOUSO", False), "ESTÁVEL"),
    ("Cão D4, febrícula isolada", ("canino", 4, True, 12), (39.3, 110, "REPOUSO", False), "ATENÇÃO"),
    ("Cão D4, febre + taquicardia + agitação", ("canino", 4, True, 4), (39.9, 152, "ALTO", False), "CRÍTICO"),
    ("Cão D4, hipertermia severa em repouso", ("canino", 4, True, 4), (40.4, 120, "REPOUSO", False), "CRÍTICO"),
    ("Cão D10, agitação sem febre", ("canino", 5, True, 10), (38.7, 105, "ALTO", False), "ATENÇÃO"),
    ("Gata D1 pós-castração, FC 170 (normal felino)", ("felino", 2, True, 1), (38.6, 170, "REPOUSO", False), "ESTÁVEL"),
    ("Gata D1, hipotermia pós-anestésica", ("felino", 2, True, 1), (36.7, 110, "REPOUSO", False), "CRÍTICO"),
    ("Gata D1, taquicardia acentuada", ("felino", 2, True, 1), (38.9, 230, "REPOUSO", False), "ATENÇÃO"),
    ("Cão idoso cardiopata, sinais normais", ("canino", 12, False, 0), (38.4, 112, "REPOUSO", False), "ESTÁVEL"),
    ("Cão idoso cardiopata, taquicardia leve", ("canino", 12, False, 0), (38.6, 150, "REPOUSO", False), "ATENÇÃO"),
    ("Cão idoso, bradicardia acentuada", ("canino", 12, False, 0), (38.0, 45, "REPOUSO", False), "CRÍTICO"),
    ("SOS do tutor com sinais normais", ("canino", 4, True, 4), (38.5, 95, "REPOUSO", True), "CRÍTICO"),
]

RAG_CASES = [
    ("febre no quinto dia depois da cirurgia", "02_febre_e_infeccao.md"),
    ("posso dar paracetamol para o meu gato", "05_medicamentos_proibidos.md"),
    ("ibuprofeno faz mal para cachorro", "05_medicamentos_proibidos.md"),
    ("gata castrada não quer comer", "08_castracao_felina.md"),
    ("cachorro operado do fêmur pulou do sofá", "07_ortopedia_osteossintese.md"),
    ("temperatura baixa depois da anestesia", "04_hipotermia_pos_anestesica.md"),
    ("convulsão e gengiva roxa", "06_sinais_de_emergencia.md"),
    ("coração acelerado depois da cirurgia dor", "03_alteracoes_cardiacas.md"),
    ("respiração rápida dormindo cão idoso cardíaco", "09_cardiopatia_geriatrica.md"),
    ("ferida vermelha com secreção e pontos", "01_cuidados_pos_operatorios.md"),
    ("o que significa prioridade P1 vermelho", "10_protocolo_triagem_clinica.md"),
    ("quanto tempo de repouso depois da cirurgia", "01_cuidados_pos_operatorios.md"),
    # mensagens com erros de digitação, como o tutor escreve no celular
    ("meu cachoro ta com febri depois da cirurgia", "02_febre_e_infeccao.md"),
    ("gatinha castrda nao qer comer", "08_castracao_felina.md"),
    ("ele ta com o coracao muito acelerdo", "03_alteracoes_cardiacas.md"),
]

GUARDRAIL_CASES = [
    ("Ele está tendo convulsão", "emergencia"), ("os pontos abriram", "emergencia"),
    ("está vomitando sangue", "emergencia"), ("a gengiva está branca", "emergencia"),
    ("posso dar paracetamol?", "medicamento"), ("dou um ibuprofeno?", "medicamento"),
    ("e dipirona de gotas?", "medicamento"), ("ele comeu bem hoje", "nenhum"),
    ("qual o horário do meloxicam?", "nenhum"), ("pode passear na guia?", "nenhum"),
    ("a gengiva dele está bem roxa", "emergencia"), ("ela desmaiou agora", "emergencia"),
    ("ele lambeu a ferida mas está tudo bem", "nenhum"),
]


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(" --- " for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-llm", action="store_true", help="roda também o cenário crítico com o Gemini (requer GEMINI_API_KEY)")
    args = parser.parse_args()
    settings = Settings()
    md = ["# Resultados da avaliação — CLYVO VET Sprint 4", "",
          "Gerado automaticamente por `python ai/evaluate.py`. Dataset sintético rotulado por regras clínicas com 4% de ruído de rótulo (ver `ai/generate_dataset.py`).", ""]

    # 1. Modelo
    metrics = train_and_save(settings.dataset_path, settings.model_path)
    md += ["## 1. Classificador de risco (Machine Learning)", "",
           f"- Linhas do dataset: **{metrics['dataset_rows']}** — distribuição: {metrics['class_distribution']}",
           f"- Modelo selecionado: **{metrics['selected_model']}** (maior F1-macro na validação cruzada 5-fold)", "",
           table(["Modelo", "F1-macro (CV média)", "Desvio"], [[k, v["cv_f1_macro_mean"], v["cv_f1_macro_std"]] for k, v in metrics["model_comparison"].items()]), "",
           "**Conjunto de teste (holdout 25%):**", "",
           table(["Métrica", "Valor"], [["Acurácia", f"{metrics['test_accuracy']:.3f}"], ["F1-macro", f"{metrics['test_f1_macro']:.3f}"],
                                        ["Recall CRÍTICO (modelo puro)", f"{metrics['test_recall_critico']:.3f}"],
                                        ["Acurácia (sistema final: modelo + dupla checagem)", f"{metrics['test_accuracy_sistema']:.3f}"],
                                        ["Recall CRÍTICO (sistema final)", f"{metrics['test_recall_critico_sistema']:.3f}"]]), "",
           "> Os rótulos do dataset têm 4% de ruído proposital (discordância entre veterinários), por isso nem o sistema final chega a 100%.", "",
           "**Matriz de confusão** (linhas = real, colunas = previsto):", "",
           table(["", "ESTÁVEL", "ATENÇÃO", "CRÍTICO"], [[lbl, *row] for lbl, row in zip(["ESTÁVEL", "ATENÇÃO", "CRÍTICO"], metrics["confusion_matrix"])]), "",
           "**Importância das variáveis:**", "",
           table(["Variável", "Importância"], list(metrics["feature_importances"].items())), ""]

    # 2. Cenários clínicos
    model = RiskModel(settings.model_path, settings.dataset_path)
    rows, hits, model_hits = [], 0, 0
    labels = {0: "ESTÁVEL", 1: "ATENÇÃO", 2: "CRÍTICO"}
    for desc, (species, age, post_op, days), (t, hr, mov, sos), expected in CLINICAL_CASES:
        pet = {"species": species, "age": age, "needs_post_op": post_op, "days_post_op": days}
        res = model.predict({"temperature": t, "heart_rate": hr, "movement_level": mov, "emergency": sos}, pet)
        ok = res["risk_label"] == expected
        hits += ok
        model_hits += labels[res["model_level"]] == expected
        rows.append([desc, f"{t}°C / {hr} BPM / {mov}{' / SOS' if sos else ''}", expected, labels[res["model_level"]],
                     res["risk_label"], "dupla checagem" if res["safety_override"] else "-", "✅" if ok else "❌"])
    md += ["## 2. Cenários clínicos de referência", "",
           f"Acerto do modelo puro: **{model_hits}/{len(CLINICAL_CASES)}** · acerto do sistema final (modelo + dupla checagem de segurança): **{hits}/{len(CLINICAL_CASES)}**", "",
           table(["Cenário", "Leitura", "Esperado", "Modelo puro", "Sistema final", "Override", ""], rows), ""]

    # 3. RAG
    kb = KnowledgeBase(settings.knowledge_dir)
    rows, h1, h3 = [], 0, 0
    for query, expected in RAG_CASES:
        sources = [r["source"] for r in kb.search(query, k=3)]
        h1 += bool(sources) and sources[0] == expected
        h3 += expected in sources
        rows.append([query, expected, sources[0] if sources else "-", "✅" if expected in sources else "❌"])
    md += ["## 3. Recuperação de protocolos (RAG)", "",
           f"- Trechos indexados: **{len(kb.chunks)}** (10 protocolos clínicos)",
           f"- **hit@1 = {h1}/{len(RAG_CASES)} ({h1 / len(RAG_CASES):.0%})** · **hit@3 = {h3}/{len(RAG_CASES)} ({h3 / len(RAG_CASES):.0%})**", "",
           table(["Pergunta do tutor", "Protocolo esperado", "1º recuperado", "Top-3"], rows), ""]

    # 4. Guardrails
    rows, ok_count = [], 0
    for text, expected in GUARDRAIL_CASES:
        got = "emergencia" if guardrails.detect_red_flags(text) else ("medicamento" if guardrails.detect_human_medication(text) else "nenhum")
        ok_count += got == expected
        rows.append([text, expected, got, "✅" if got == expected else "❌"])
    md += ["## 4. Guardrails do assistente", "", f"Acerto: **{ok_count}/{len(GUARDRAIL_CASES)}**", "",
           table(["Mensagem", "Esperado", "Detectado", ""], rows), ""]

    # 5. Pipeline ponta a ponta
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = Settings()
        s.db_path, s.llm_provider, s.alert_cooldown_minutes = str(Path(tmp) / "eval.db"), "offline", 0
        client = TestClient(create_app(s))
        rows = []
        for scenario, pet_id in [("normal", 1), ("atencao", 1), ("critico", 1), ("sos", 3), ("hipotermia", 2)]:
            start = time.perf_counter()
            res = client.post(f"/api/simulate/{scenario}?pet_id={pet_id}").json()[0]
            ms = (time.perf_counter() - start) * 1000
            alert = res["alert"]
            rows.append([scenario, res["pet_name"], res["risk"]["risk_label"], "sim" if alert else "não",
                         len(alert["soap"]["plano"]) if alert else "-", ", ".join(alert["citations"]) if alert else "-", f"{ms:.0f} ms"])
        sample = client.post("/api/simulate/critico?pet_id=1").json()[0]["alert"]
        md += ["## 5. Pipeline ponta a ponta (IoT → ML → RAG → IA Generativa → notificação)", "",
               "Executado com a IA generativa em modo offline (determinístico) para medir a latência do pipeline sem rede.", "",
               table(["Cenário", "Pet", "Risco", "Alerta", "Itens no plano SOAP", "Protocolos citados", "Latência"], rows), "",
               "### Exemplo de alerta gerado (cenário crítico — Thor)", "", "```text", sample["tutor_message"], "```", "",
               "```text", f"S: {sample['soap']['subjetivo']}", f"O: {sample['soap']['objetivo']}", f"A: {sample['soap']['avaliacao']}",
               "P: " + " | ".join(sample["soap"]["plano"]), "```", ""]

        if args.with_llm:
            s.db_path, s.llm_provider = str(Path(tmp) / "eval_llm.db"), "gemini"
            llm_client = TestClient(create_app(s))
            start = time.perf_counter()
            alert = llm_client.post("/api/simulate/critico?pet_id=1").json()[0]["alert"]
            ms = (time.perf_counter() - start) * 1000
            chat = llm_client.post("/api/pets/1/chat", json={"message": "Ele está ofegante e não quer comer, o que eu faço?"}).json()
            md += ["## 6. Execução com o Gemini (IA Generativa online)", "", f"Gerado por: **{alert['llm_mode']}** em {ms:.0f} ms", "",
                   "```text", alert["tutor_message"], "```", "", "```text", f"S: {alert['soap']['subjetivo']}", f"O: {alert['soap']['objetivo']}",
                   f"A: {alert['soap']['avaliacao']}", "P: " + " | ".join(alert["soap"]["plano"]), "```", "",
                   "**Chat do tutor** — _Ele está ofegante e não quer comer, o que eu faço?_", "", "```text", chat["answer"], "```", ""]

    out = BASE_DIR / "docs" / "RESULTADOS.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"Relatório salvo em {out}")
    print(f"Modelo: acc={metrics['test_accuracy']:.3f} f1={metrics['test_f1_macro']:.3f} recall_critico={metrics['test_recall_critico']:.3f} (sistema {metrics['test_recall_critico_sistema']:.3f}) | "
          f"cenários modelo {model_hits}/{len(CLINICAL_CASES)} sistema {hits}/{len(CLINICAL_CASES)} | RAG hit@1 {h1}/{len(RAG_CASES)} hit@3 {h3}/{len(RAG_CASES)} | guardrails {ok_count}/{len(GUARDRAIL_CASES)}")


if __name__ == "__main__":
    main()
