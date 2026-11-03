"""Recuperação de conhecimento clínico (o "R" do RAG).

A base de conhecimento são os protocolos em ai/data/knowledge/*.md. Cada seção "## ..." vira um
trecho (chunk) indexado por busca híbrida: TF-IDF de palavras (unigramas + bigramas, sem acentos) somado
a TF-IDF de n-gramas de caracteres (3 a 5), que tolera variações como "pulou"/"pular" e erros de
digitação do tutor. Os trechos mais similares (cosseno) são devolvidos com um identificador [K1],
[K2]... para a IA Generativa citar a fonte.

O prontuário do paciente (MySQL/SQLite) é a segunda fonte de contexto e é recuperado por SQL no
copiloto; aqui fica apenas a busca semântica nos protocolos.
"""
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

PT_STOPWORDS = """a o e é de da do das dos em no na nos nas um uma uns umas por para com sem que se ao aos
à às ou mais menos muito pouco como quando onde qual quais ser estar ter há pode deve devem entre até
seu sua seus suas meu minha isso este esta esse essa ele ela eles elas pelo pela pelos pelas já não sim
também foi são está estão tem""".split()
# O vetorizador remove acentos antes de tokenizar, então as stopwords precisam estar sem acento também
PT_STOPWORDS = sorted({"".join(ch for ch in unicodedata.normalize("NFKD", w) if not unicodedata.combining(ch)) for w in PT_STOPWORDS})

WORD_WEIGHT = 0.5  # peso da similaridade por palavras na busca híbrida (o restante vai para n-gramas de caracteres)


@dataclass
class Chunk:
    id: str
    source: str
    title: str
    text: str


class KnowledgeBase:
    def __init__(self, knowledge_dir: str):
        self.chunks = self._load_chunks(Path(knowledge_dir))
        docs = [f"{c.title} {c.title} {c.text}" for c in self.chunks]
        self.word_vectorizer = TfidfVectorizer(strip_accents="unicode", lowercase=True, ngram_range=(1, 2),
                                               sublinear_tf=True, stop_words=PT_STOPWORDS)
        self.char_vectorizer = TfidfVectorizer(strip_accents="unicode", lowercase=True, analyzer="char_wb",
                                               ngram_range=(3, 5), sublinear_tf=True)
        self.word_matrix = self.word_vectorizer.fit_transform(docs)
        self.char_matrix = self.char_vectorizer.fit_transform(docs)

    @staticmethod
    def _load_chunks(folder: Path) -> list:
        chunks = []
        for path in sorted(folder.glob("*.md")):
            content = path.read_text(encoding="utf-8")
            doc_title = (re.search(r"^# (.+)$", content, re.M) or [None, path.stem])[1]
            for i, section in enumerate(re.split(r"^## ", content, flags=re.M)[1:], start=1):
                heading, _, body = section.partition("\n")
                chunks.append(Chunk(id=f"{path.stem}#{i}", source=path.name,
                                    title=f"{doc_title} > {heading.strip()}", text=" ".join(body.split())))
        return chunks

    def search(self, query: str, k: int = 4, min_score: float = 0.02) -> list:
        if not query.strip():
            return []
        scores = (WORD_WEIGHT * cosine_similarity(self.word_vectorizer.transform([query]), self.word_matrix)[0]
                  + (1 - WORD_WEIGHT) * cosine_similarity(self.char_vectorizer.transform([query]), self.char_matrix)[0])
        ranked = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
        results = []
        for rank, idx in enumerate(ranked, start=1):
            if scores[idx] < min_score:
                continue
            c = self.chunks[idx]
            results.append({"ref": f"K{rank}", "id": c.id, "source": c.source, "title": c.title,
                            "text": c.text, "score": round(float(scores[idx]), 4)})
        return results

    @staticmethod
    def format_context(results: list) -> str:
        return "\n".join(f"[{r['ref']}] {r['title']}: {r['text']}" for r in results) or "(nenhum protocolo relevante encontrado)"
