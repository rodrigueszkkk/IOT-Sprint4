"""Barreiras de segurança (guardrails) da IA conversacional e dos alertas.

1. Entrada: detecta sinais de emergência no texto do tutor -> escalonamento imediato (P1),
   sem depender do LLM.
2. Entrada: detecta perguntas sobre medicamentos humanos/doses -> resposta segura padronizada.
3. Saída: remove doses (mg, ml, comprimidos) que não estejam na prescrição do prontuário e
   garante o aviso de que a IA não substitui o veterinário.
"""
import re
import unicodedata

# Padrões (regex sobre texto sem acentos) -> sinal de emergência. "(\w+ ){0,3}" tolera palavras no meio,
# ex.: "a gengiva dele está branca".
RED_FLAGS = {
    r"convuls|ataque epilet": "convulsão",
    r"nao (consegue )?respira|falta de ar|dificuldade (para|de) respirar|sufocando": "dificuldade respiratória",
    r"respirando com a boca aberta": "respiração de boca aberta",
    r"gengiva(s)? (\w+ ){0,3}(roxa|azul|azulada|cinza)": "mucosas cianóticas",
    r"gengiva(s)? (\w+ ){0,3}(branca|palida)": "mucosas pálidas",
    r"sangra(ndo|mento)": "sangramento",
    r"pontos (\w+ ){0,1}(abriram|soltaram|arrebentaram)|ferida (\w+ ){0,1}abriu|abriu (a ferida|os pontos)": "deiscência de sutura",
    r"desmai|desacordad|inconscient|nao acorda": "síncope / inconsciência",
    r"vomit\w* (\w+ ){0,1}sangue": "hematêmese",
    r"envenen|veneno|chumbinho": "intoxicação",
    r"nao para de chorar|gritando de dor|uivando de dor": "dor intensa",
}

HUMAN_MEDS = ["paracetamol", "tylenol", "ibuprofeno", "advil", "naproxeno", "diclofenaco", "cataflam",
              "voltaren", "aspirina", "aas", "acido acetilsalicilico", "dipirona", "novalgina"]

DOSE_PATTERN = re.compile(r"\b\d+[.,]?\d*\s*(mg|ml|mL|g|gotas?|comprimidos?|cp)\b(\s*/\s*kg)?", re.I)
DISCLAIMER = "Esta orientação é um apoio da IA CLYVO VET e não substitui a avaliação do médico-veterinário."


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def detect_red_flags(text: str) -> list:
    norm = normalize(text)
    found = []
    for pattern, label in RED_FLAGS.items():
        if re.search(pattern, norm) and label not in found:
            found.append(label)
    return found


def detect_human_medication(text: str) -> list:
    norm = normalize(text)
    return [m for m in HUMAN_MEDS if re.search(rf"\b{re.escape(m)}\b", norm)]


def medication_safe_reply(pet_name: str, meds: list, species: str) -> str:
    meds_txt = ", ".join(sorted(set(meds)))
    extra = " Para gatos, o paracetamol é fatal mesmo em doses mínimas." if species.lower() == "felino" else ""
    return (f"Não ofereça {meds_txt} ao {pet_name} sem orientação do veterinário. Medicamentos de uso humano "
            f"podem causar úlcera, sangramento, lesão no fígado e nos rins em pets, e somam risco com o "
            f"anti-inflamatório que já foi prescrito.{extra} Se ele parecer com dor, me conte o que está "
            f"observando que eu aviso a equipe da clínica para ajustar a medicação com segurança.")


def sanitize_output(text: str, allowed_context: str) -> str:
    """Remove doses que não aparecem literalmente no prontuário (prescrição) e garante o aviso legal."""
    allowed = normalize(allowed_context)

    def _replace(match):
        return match.group(0) if normalize(match.group(0)) in allowed else "[dose definida pelo veterinário]"

    clean = DOSE_PATTERN.sub(_replace, text)
    if DISCLAIMER not in clean:
        clean = f"{clean.rstrip()}\n\n_{DISCLAIMER}_"
    return clean
