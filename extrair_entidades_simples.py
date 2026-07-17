"""
Script de Exemplo: Extração Simples de Nomes e Documentos
===========================================================

Este script demonstra o uso isolado das funções de extração de
CPF/CNPJ e de resgate de nomes a partir de um texto de petição.

Uso:
1. Certifique-se de que seu ambiente virtual está ativo.
2. Execute o script a partir da raiz do projeto:
   python -m src.scripts.extrair_entidades_simples

O que ele faz:
- Pega um texto de exemplo (`PETICAO_EXEMPLO`).
- Usa `extract_documents` para encontrar todos os CPFs e CNPJs válidos no texto.
- Para cada documento encontrado, usa `extract_name_preceding_doc` para
  encontrar o nome da parte que o antecede no texto.
- Imprime os resultados de forma estruturada.
"""
import os
import sys
import pandas as pd
import json

# Adiciona a raiz do projeto ao sys.path para permitir importações relativas
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    # Tenta importar as funções necessárias da estrutura 'src'
    from extractors.cpf_cnpj_extractor import extract_documents
    from comparators.polo_compare import extract_name_preceding_doc
except ImportError as e:
    print(f"Erro de importação: {e}")
    print("Verifique se o script está sendo executado a partir da raiz do projeto e se os módulos existem.")
    sys.exit(1)

if __name__ == "__main__":
    
    df = pd.read_parquet(r"C:\Users\lfmelo\Documents\Github\TJGO_Projeto-Processos-Pessoas-Vulneraveis\data\dados_processos_guarda_vulneraveis-14072026.parquet")

    entidades = {}
    for row in df.itertuples():
        # 1. Extrai todos os documentos (CPFs e CNPJs) do texto
        documentos_encontrados = extract_documents(row.inteiro_teor)

        todos_docs = documentos_encontrados.get('cnpjs', set()) | documentos_encontrados.get('cpfs', set())
        # 2. Para cada documento, extrai o nome que o antecede
        for doc in todos_docs:
            nome_extraido = extract_name_preceding_doc(row.inteiro_teor, doc)
            entidades.update({doc: nome_extraido})
            #print(f"Documento: {doc}, Nome Extraído: {nome_extraido}")

    with open('data/entidades_cpf_nome_300.json', 'w', encoding='utf-8') as f:
        json.dump(entidades,f, ensure_ascii=False, indent=4)
        f.close()
        
    print(f"Foram encontrados e extraidos {len(entidades)} nomes e documentos")
    

