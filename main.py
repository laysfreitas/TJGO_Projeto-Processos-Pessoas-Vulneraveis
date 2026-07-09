import modeling.hypermatch as hp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import itertools
import pandas as pd

from tqdm.auto import tqdm


def achar_pares_parecidos_dataset(
    df: pd.DataFrame,
    id_col: str = "id_processo",
    text_col: str = "inteiro_teor_lematizado",
    top_k: int = 20,
    pre_candidatos: int = 300,
    mostrar_progresso: bool = True
) -> pd.DataFrame:

    base = df[[id_col, text_col]].dropna().copy()
    base[text_col] = base[text_col].astype(str)

    ids = base[id_col].tolist()
    textos = base[text_col].tolist()

    print("Calculando matriz TF-IDF global...")

    vec = TfidfVectorizer(
        tokenizer=hp.tokens_lematizados,
        token_pattern=None,
        max_features=100_000,
        min_df=1,
        max_df=1.0
    )

    X = vec.fit_transform(textos)

    print("Calculando similaridade global...")

    sim = cosine_similarity(X)

    print("Selecionando candidatos...")

    candidatos = []

    pares_iter = itertools.combinations(range(len(ids)), 2)
    total_pares = len(ids) * (len(ids) - 1) // 2

    if mostrar_progresso:
        pares_iter = tqdm(
            pares_iter,
            total=total_pares,
            desc="Gerando pares candidatos"
        )

    for i, j in pares_iter:
        candidatos.append({
            "idx_1": i,
            "idx_2": j,
            "doc_1": ids[i],
            "doc_2": ids[j],
            "score_tfidf_global": float(sim[i, j])
        })

    candidatos = sorted(
        candidatos,
        key=lambda x: x["score_tfidf_global"],
        reverse=True
    )[:pre_candidatos]

    print(f"Calculando HyperMatch-lite para {len(candidatos)} candidatos...")

    resultados = []

    candidatos_iter = candidatos

    if mostrar_progresso:
        candidatos_iter = tqdm(
            candidatos,
            total=len(candidatos),
            desc="Calculando score HyperMatch-lite"
        )

    for c in candidatos_iter:
        i = c["idx_1"]
        j = c["idx_2"]

        score_hyper = hp.score_hypermatch_lematizado(
            textos[i],
            textos[j],
            n_keywords=30,
            chunk_size=120,
            chunk_overlap=30
        )

        resultados.append({
            "doc_1": c["doc_1"],
            "doc_2": c["doc_2"],
            "score_hypermatch_lematizado": round(score_hyper, 4),
            "score_tfidf_global": round(c["score_tfidf_global"], 4)
        })

    return (
        pd.DataFrame(resultados)
        .sort_values("score_hypermatch_lematizado", ascending=False)
        .head(top_k)
        .reset_index(drop=True)
    )

df_atual = pd.read_parquet(r"C:\Users\lfmelo\Documents\Github\TJGO_ThemeClassification-1\TJGO_Projeto-Processos-Pessoas-Vulneraveis\data\dataset_enriquecido_10062026_lematizado.parquet")
df = df_atual.reset_index().rename(columns={"index": "id"})

print(df.head())

pares = achar_pares_parecidos_dataset(
    df,
    id_col="id",
    text_col="inteiro_teor_lematizado",
    top_k=30,
    pre_candidatos=500,
    mostrar_progresso=True
)

pares.to_parquet(r"C:\Users\lfmelo\Documents\Github\TJGO_Projeto-Processos-Pessoas-Vulneraveis\data\pares_parecidos.parquet")