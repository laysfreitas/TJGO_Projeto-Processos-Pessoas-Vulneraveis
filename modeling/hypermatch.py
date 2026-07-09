import itertools
import math
from collections import Counter
from typing import List, Dict

import numpy as np
import pandas as pd
import networkx as nx

from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity

"""Funções de lematização"""
def tokens_lematizados(texto: str) -> List[str]:
    """
    Como o texto já está lematizado, assumimos que os tokens já vêm separados por espaço.
    """
    if pd.isna(texto):
        return []
    return [t for t in str(texto).lower().split() if len(t) > 2]


def chunks_por_tokens(texto: str, tamanho: int = 120, sobreposicao: int = 30) -> List[str]:
    """
    Substitui a ideia de 'sentenças' do artigo quando só temos texto lematizado contínuo.
    Cada chunk funciona como uma unidade semântica local.
    """
    if pd.isna(texto):
        return []

    toks = tokens_lematizados(texto)
    if not toks:
        return []

    passo = max(1, tamanho - sobreposicao)
    chunks = []

    for i in range(0, len(toks), passo):
        bloco = toks[i:i + tamanho]
        if len(bloco) >= 10:
            chunks.append(" ".join(bloco))

    return chunks


def extrair_keywords_tfidf(textos, top_n=30):
    """
    Extrai termos relevantes para cada documento.
    Versão robusta para comparação par-a-par com apenas 2 documentos.
    """

    textos = ["" if pd.isna(t) else str(t) for t in textos]

    # Verificação simples para evitar erro quando os textos estão vazios
    if all(len(tokens_lematizados(t)) == 0 for t in textos):
        return {i: [] for i in range(len(textos))}

    vectorizer = TfidfVectorizer(
        tokenizer=tokens_lematizados,
        token_pattern=None,
        min_df=1,
        max_df=1.0  # importante: não remover termos compartilhados no par
    )

    try:
        X = vectorizer.fit_transform(textos)
    except ValueError:
        # fallback caso o vocabulário fique vazio por algum motivo
        return {
            i: [termo for termo, _ in Counter(tokens_lematizados(texto)).most_common(top_n)]
            for i, texto in enumerate(textos)
        }

    termos = np.array(vectorizer.get_feature_names_out())
    keywords_por_doc = {}

    for i in range(X.shape[0]):
        linha = X[i].toarray().ravel()

        if linha.sum() == 0:
            keywords_por_doc[i] = [
                termo for termo, _ in Counter(tokens_lematizados(textos[i])).most_common(top_n)
            ]
            continue

        top_idx = linha.argsort()[::-1][:top_n]
        keywords_por_doc[i] = termos[top_idx].tolist()

    return keywords_por_doc

"""
Funções de similaridade 
"""
def cosine_tf(t1: str, t2: str) -> float:
    if not t1.strip() or not t2.strip():
        return 0.0

    vec = CountVectorizer(
        tokenizer=tokens_lematizados,
        token_pattern=None
    )

    X = vec.fit_transform([t1, t2])
    return float(cosine_similarity(X[0], X[1])[0, 0])


def cosine_tfidf(t1: str, t2: str) -> float:
    if not t1.strip() or not t2.strip():
        return 0.0

    vec = TfidfVectorizer(
        tokenizer=tokens_lematizados,
        token_pattern=None
    )

    X = vec.fit_transform([t1, t2])
    return float(cosine_similarity(X[0], X[1])[0, 0])


def jaccard(t1: str, t2: str) -> float:
    a = set(tokens_lematizados(t1))
    b = set(tokens_lematizados(t2))

    if not a or not b:
        return 0.0

    return len(a & b) / len(a | b)


def ochiai(t1: str, t2: str) -> float:
    a = set(tokens_lematizados(t1))
    b = set(tokens_lematizados(t2))

    if not a or not b:
        return 0.0

    return len(a & b) / math.sqrt(len(a) * len(b))


def bm25_like(t1: str, t2: str, k1: float = 1.5, b: float = 0.75) -> float:
    """
    BM25 simplificado e simétrico.
    Bom para capturar sobreposição ponderada entre dois blocos textuais.
    """
    d1 = tokens_lematizados(t1)
    d2 = tokens_lematizados(t2)

    if not d1 or not d2:
        return 0.0

    docs = [d1, d2]
    avgdl = np.mean([len(d) for d in docs])
    vocab = set(d1) | set(d2)

    df = {
        termo: sum(termo in set(doc) for doc in docs)
        for termo in vocab
    }

    idf = {
        termo: math.log(1 + (2 - df[termo] + 0.5) / (df[termo] + 0.5))
        for termo in vocab
    }

    def score(query, doc):
        freq = Counter(doc)
        dl = len(doc)
        total = 0.0

        for termo in query:
            if termo not in freq:
                continue

            tf = freq[termo]
            denom = tf + k1 * (1 - b + b * dl / avgdl)
            total += idf.get(termo, 0.0) * (tf * (k1 + 1)) / denom

        return total

    bruto = 0.5 * (score(d1, d2) + score(d2, d1))
    return bruto / (1.0 + bruto)


def vetor_similaridade_local(t1: str, t2: str) -> np.ndarray:
    """
    Aproxima o S_similarity do artigo:
    TF cosine, TF-IDF cosine, BM25, Ochiai e Jaccard.
    """
    return np.array([
        cosine_tf(t1, t2),
        cosine_tfidf(t1, t2),
        bm25_like(t1, t2),
        ochiai(t1, t2),
        jaccard(t1, t2)
    ], dtype=float)


def score_hypermatch_lematizado(
    doc1_lem: str,
    doc2_lem: str,
    n_keywords: int = 30,
    chunk_size: int = 120,
    chunk_overlap: int = 30,
    n_layers: int = 2
) -> float:
    """
    Versão não supervisionada inspirada no HyperMatch para textos já lematizados.
    """

    chunks1 = chunks_por_tokens(doc1_lem, tamanho=chunk_size, sobreposicao=chunk_overlap)
    chunks2 = chunks_por_tokens(doc2_lem, tamanho=chunk_size, sobreposicao=chunk_overlap)

    if not chunks1 or not chunks2:
        return float(np.mean(vetor_similaridade_local(doc1_lem, doc2_lem)))

    # Palavras-chave extraídas do par de documentos.
    keywords_dict = extrair_keywords_tfidf([doc1_lem, doc2_lem], top_n=n_keywords)
    keywords = list(dict.fromkeys(keywords_dict[0] + keywords_dict[1]))

    node_texts_global = []
    node_features = []

    for kw in keywords:
        # Anexação de unidades textuais ao nó, como no artigo.
        c1_kw = [c for c in chunks1 if kw in c.split()]
        c2_kw = [c for c in chunks2 if kw in c.split()]

        if not c1_kw and not c2_kw:
            continue

        t1_kw = " ".join(c1_kw)
        t2_kw = " ".join(c2_kw)

        node_texts_global.append(t1_kw + " " + t2_kw)
        node_features.append(vetor_similaridade_local(t1_kw, t2_kw))

    if len(node_features) < 2:
        return float(np.mean(vetor_similaridade_local(doc1_lem, doc2_lem)))

    node_features = np.vstack(node_features)

    # Grafo de palavras-chave: similaridade TF-IDF entre os textos associados a cada nó.
    vec = TfidfVectorizer(
        tokenizer=tokens_lematizados,
        token_pattern=None
    )

    X_nodes = vec.fit_transform(node_texts_global)
    A = cosine_similarity(X_nodes)
    np.fill_diagonal(A, 0.0)

    # Limiar k: média dos elementos não nulos, como na construção do hipergrafo.
    nonzero = A[A > 0]
    threshold = float(nonzero.mean()) if len(nonzero) else 0.0

    # Hiperarestas: cada nó âncora agrupa nós similares acima do limiar.
    hyperedges = []

    for i in range(A.shape[0]):
        grupo = set(np.where(A[i] > threshold)[0])
        grupo.add(i)

        if len(grupo) >= 2:
            hyperedges.append(grupo)

    # Aproximação HyperGCN-lite:
    # converte hiperarestas em conexões ponderadas entre nós.
    H = np.zeros_like(A)

    for edge in hyperedges:
        for u, v in itertools.combinations(edge, 2):
            peso = A[u, v] if A[u, v] > 0 else 1.0 / len(edge)
            H[u, v] += peso
            H[v, u] += peso

    row_sum = H.sum(axis=1, keepdims=True)
    H_norm = np.divide(H, row_sum, out=np.zeros_like(H), where=row_sum != 0)

    F = node_features.copy()
    alpha = 0.65

    for _ in range(n_layers):
        F = alpha * F + (1 - alpha) * (H_norm @ F)

    # Peso dos nós por PageRank, semelhante à ideia de ponderar nós importantes.
    G = nx.from_numpy_array(A)

    if G.number_of_edges() > 0:
        pr = nx.pagerank(G, weight="weight")
        weights = np.array([pr[i] for i in range(len(pr))], dtype=float)
        weights = weights / weights.sum()
    else:
        weights = np.ones(F.shape[0]) / F.shape[0]

    score_local_hipergrafo = float(np.mean(weights @ F))
    score_global = float(np.mean(vetor_similaridade_local(doc1_lem, doc2_lem)))

    return 0.70 * score_local_hipergrafo + 0.30 * score_global