from networkx.algorithms import dominance
import pandas as pd
import spacy

import re

import extractors.cpf_cnpj_extractor as cpf_ext
from extractors.metadata_extractor import MetadataExtractor


nlp = spacy.load("pt_core_news_lg")
pd.set_option('display.max_colwidth', None)

df = pd.read_parquet(r"C:\Users\lfmelo\Documents\Github\TJGO_Projeto-Processos-Pessoas-Vulneraveis\data\dados_processos_guarda_vulneraveis-14072026.parquet")

def extracao_nomes(texto) -> list[str]:
    """
    Args:
        texto: petição inicial em texto plano (após `clean_text`).

    Returns:
        `list[str]` com nomes.
    """
    doc = nlp(texto)
    nomes = [ent.text for ent in doc.ents if ent.label_ == "PER"]

    return nomes

df['cpf_cnpj_polo_ativo'] = df['cpf_cnpj_polo_ativo'].apply(lambda x: x.split("#"))
df['cpf_cnpj_polo_passivo'] = df['cpf_cnpj_polo_passivo'].apply(lambda x: x.split("#"))

df = df.explode('cpf_cnpj_polo_ativo').reset_index(drop=True)
df = df.explode('cpf_cnpj_polo_passivo').reset_index(drop=True)

df = df.astype(str)

df.to_csv(r'C:\Users\lfmelo\Documents\Github\TJGO_Projeto-Processos-Pessoas-Vulneraveis\data\dados_processos_guarda_vulneraveis.csv', index=False , encoding='utf-8')

for i in df.itertuples():
    peticao = df.inteiro_teor
    print(peticao)
    if pd.isna(peticao):
        peticao_limpa = ""
    else:
        s = str(peticao).replace(">>>>>inicio<<<<<", "")
        s = re.sub(r"#####fim#####.*", "", s)
        peticao_limpa = re.sub(r'\s+', ' ', s).strip()
        
    processor = MetadataExtractor(peticao_limpa)

    entidades_extraidas = processor.get_entidades()
    print(entidades_extraidas)