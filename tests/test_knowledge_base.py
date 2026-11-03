"""Validação da recuperação de protocolos (RAG)."""
import pytest


@pytest.mark.parametrize("query,expected_source", [
    ("febre no quinto dia depois da cirurgia infecção", "02_febre_e_infeccao.md"),
    ("posso dar paracetamol para o meu gato", "05_medicamentos_proibidos.md"),
    ("gata castrada não quer comer depois da cirurgia", "08_castracao_felina.md"),
    ("cachorro operado do fêmur pulou do sofá implante", "07_ortopedia_osteossintese.md"),
    ("temperatura baixa e tremendo depois da anestesia", "04_hipotermia_pos_anestesica.md"),
    ("convulsão e gengiva roxa", "06_sinais_de_emergencia.md"),
])
def test_recupera_protocolo_correto_no_top3(kb, query, expected_source):
    results = kb.search(query, k=3)
    assert expected_source in [r["source"] for r in results]


def test_resultados_numerados_para_citacao(kb):
    results = kb.search("taquicardia dor pós-operatória", k=3)
    assert [r["ref"] for r in results] == ["K1", "K2", "K3"][: len(results)]
    assert "[K1]" in kb.format_context(results)


def test_consulta_vazia(kb):
    assert kb.search("   ") == []
