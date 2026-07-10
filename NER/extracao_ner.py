import re
import json
import spacy
from pathlib import Path
import pandas as pd

from tqdm.auto import tqdm


# =========================
# 1. Carregar modelo spaCy
# =========================

nlp = spacy.load(
    "pt_core_news_lg",
    disable=["parser", "lemmatizer", "attribute_ruler"]
)

def dividir_texto_em_blocos(texto, tamanho_maximo=50_000, sobreposicao=200):
    """
    Divide o texto em blocos com limite real de caracteres.

    Garante que nenhum bloco ultrapasse tamanho_maximo,
    mesmo quando o texto vem como uma linha única gigante.
    """
    if not isinstance(texto, str) or not texto:
        return []

    if tamanho_maximo <= 0:
        raise ValueError("tamanho_maximo precisa ser maior que zero")

    blocos = []
    n = len(texto)
    inicio = 0

    while inicio < n:
        fim = min(inicio + tamanho_maximo, n)

        # Tenta cortar em um ponto natural, mas sem deixar o bloco pequeno demais
        if fim < n:
            janela = texto[inicio:fim]
            limite_minimo = int(tamanho_maximo * 0.60)

            candidatos = [
                janela.rfind("\n\n"),
                janela.rfind("\n"),
                janela.rfind(". "),
                janela.rfind("; "),
                janela.rfind(", "),
                janela.rfind(" "),
            ]

            candidatos_validos = [c for c in candidatos if c >= limite_minimo]

            if candidatos_validos:
                fim = inicio + max(candidatos_validos) + 1

        bloco = texto[inicio:fim]

        if bloco.strip():
            blocos.append((bloco, inicio))

        if fim >= n:
            break

        proximo_inicio = fim - sobreposicao

        if proximo_inicio <= inicio:
            proximo_inicio = fim

        inicio = proximo_inicio

    return blocos
# =========================
# 2. Regex principais
# =========================

REGEX_PROCESSO_CNJ = r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b"

REGEX_CPF = r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"

REGEX_CNPJ = r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"

REGEX_OAB = r"\bOAB\s*/?\s*[A-Z]{2}\s*n?[º°]?\s*\d{1,6}\b|\bOAB\s*n?[º°]?\s*\d{1,6}\s*/?\s*[A-Z]{2}\b"

REGEX_CLASSE_LINHA = r"(?im)^\s*Classe(?:\s+Processual)?\s*[:\-]\s*(.+)$"

REGEX_ASSUNTO_LINHA = r"(?im)^\s*Assunto(?:s)?\s*[:\-]\s*(.+)$"

REGEX_COMARCA = r"(?i)\bComarca\s+de\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][\wÁÀÂÃÉÊÍÓÔÕÚÇáàâãéêíóôõúç\s\-]+)"

REGEX_VARA = r"(?i)\b\d{1,2}[ªº]?\s+Vara\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇa-záàâãéêíóôõúç\s\-]+"

REGEX_PARTES = {
    "AUTOR": r"(?im)^\s*(Autor|Autora|Requerente|Exequente|Impetrante)\s*[:\-]\s*(.+)$",
    "REU": r"(?im)^\s*(Réu|Requerido|Requerida|Executado|Executada|Impetrado|Impetrada)\s*[:\-]\s*(.+)$",
    "ADVOGADO": r"(?im)^\s*(Advogado|Advogada|Procurador|Procuradora)\s*[:\-]\s*(.+)$",
}


CLASSES_CONHECIDAS = [
    "ação civil pública",
    "ação de alimentos",
    "ação de cobrança",
    "ação de indenização",
    "ação de obrigação de fazer",
    "ação declaratória",
    "ação monitória",
    "ação ordinária",
    "agravo de instrumento",
    "apelação cível",
    "cumprimento de sentença",
    "divórcio litigioso",
    "execução fiscal",
    "habeas corpus",
    "inventário",
    "mandado de segurança",
    "procedimento comum cível",
    "reclamação",
    "tutela cautelar antecedente",
]


ASSUNTOS_CONHECIDOS = [
    "idoso",
    "pessoa com deficiência",
    "criança e adolescente",
    "saúde",
    "fornecimento de medicamento",
    "internação",
    "violência doméstica",
    "alimentos",
    "guarda",
    "curatela",
    "interdição",
    "benefício assistencial",
    "bpc",
    "previdenciário",
    "dano moral",
    "indenização",
]


# =========================
# 3. Funções auxiliares
# =========================

def limpar_texto(texto: str) -> str:
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def normalizar_espacos(valor: str) -> str:
    return re.sub(r"\s+", " ", valor).strip()


def somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor)


def validar_cpf(cpf: str) -> bool:
    cpf = somente_digitos(cpf)

    if len(cpf) != 11:
        return False

    if cpf == cpf[0] * 11:
        return False

    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    digito_1 = (soma * 10) % 11
    digito_1 = 0 if digito_1 == 10 else digito_1

    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    digito_2 = (soma * 10) % 11
    digito_2 = 0 if digito_2 == 10 else digito_2

    return cpf[-2:] == f"{digito_1}{digito_2}"


def mascarar_cpf(cpf: str) -> str:
    cpf = somente_digitos(cpf)

    if len(cpf) != 11:
        return cpf

    return f"{cpf[:3]}.***.***-{cpf[-2:]}"


def extrair_por_regex(texto: str, regex: str, label: str, validar=None, mascarar=False):
    entidades = []

    for match in re.finditer(regex, texto):
        valor_original = match.group(0)
        valor_limpo = normalizar_espacos(valor_original)

        if validar and not validar(valor_limpo):
            continue

        if mascarar and label == "CPF":
            valor_saida = mascarar_cpf(valor_limpo)
        else:
            valor_saida = valor_limpo

        entidades.append({
            "label": label,
            "texto": valor_saida,
            "inicio": match.start(),
            "fim": match.end(),
            "origem": "regex"
        })

    return entidades


def extrair_linhas_chave(texto: str, regex: str, label: str):
    entidades = []

    for match in re.finditer(regex, texto):
        valor = normalizar_espacos(match.group(1))

        if valor:
            entidades.append({
                "label": label,
                "texto": valor,
                "inicio": match.start(1),
                "fim": match.end(1),
                "origem": "regex_linha"
            })

    return entidades


def extrair_lista_termos(texto: str, termos: list[str], label: str):
    entidades = []
    texto_lower = texto.lower()

    for termo in termos:
        for match in re.finditer(re.escape(termo.lower()), texto_lower):
            entidades.append({
                "label": label,
                "texto": texto[match.start():match.end()],
                "inicio": match.start(),
                "fim": match.end(),
                "origem": "lista_termos"
            })

    return entidades


def extrair_partes(texto: str):
    entidades = []

    for label, regex in REGEX_PARTES.items():
        for match in re.finditer(regex, texto):
            tipo_campo = normalizar_espacos(match.group(1))
            nome = normalizar_espacos(match.group(2))

            entidades.append({
                "label": label,
                "campo": tipo_campo,
                "texto": nome,
                "inicio": match.start(2),
                "fim": match.end(2),
                "origem": "regex_partes"
            })

    return entidades


def extrair_spacy(texto, tamanho_bloco=50_000):
    entidades = []

    if not isinstance(texto, str) or not texto.strip():
        return entidades

    blocos = dividir_texto_em_blocos(
        texto,
        tamanho_maximo=tamanho_bloco,
        sobreposicao=200
    )

    # Verificação defensiva
    maior_bloco = max((len(bloco) for bloco, _ in blocos), default=0)

    if maior_bloco > nlp.max_length:
        raise ValueError(
            f"Chunk maior que o limite do spaCy. "
            f"maior_bloco={maior_bloco}, nlp.max_length={nlp.max_length}"
        )

    textos_blocos = (bloco for bloco, _ in blocos)

    for (bloco, offset), doc in zip(
        blocos,
        nlp.pipe(textos_blocos, batch_size=4)
    ):
        for ent in doc.ents:
            entidades.append({
                "texto": ent.text,
                "label": ent.label_,
                "inicio": ent.start_char + offset,
                "fim": ent.end_char + offset,
                "origem": "spacy"
            })

    return entidades


def remover_duplicados(entidades):
    vistos = set()
    resultado = []

    for ent in entidades:
        chave = (
            ent.get("label"),
            ent.get("texto", "").lower(),
            ent.get("inicio"),
            ent.get("fim")
        )

        if chave not in vistos:
            vistos.add(chave)
            resultado.append(ent)

    return resultado


def associar_entidades_ao_processo(entidades):
    processos = [e for e in entidades if e["label"] == "PROCESSO_CNJ"]

    if not processos:
        for ent in entidades:
            ent["processo_vinculado"] = None
        return entidades

    for ent in entidades:
        if ent["label"] == "PROCESSO_CNJ":
            ent["processo_vinculado"] = ent["texto"]
            continue

        processo_mais_proximo = min(
            processos,
            key=lambda p: abs(ent["inicio"] - p["inicio"])
        )

        ent["processo_vinculado"] = processo_mais_proximo["texto"]

    return entidades


# =========================
# 4. Função principal
# =========================

def extrair_entidades_juridicas(texto: str, mascarar_dados_sensiveis: bool = False):
    texto = limpar_texto(texto)

    entidades = []

    # Identificadores fortes
    entidades += extrair_por_regex(texto, REGEX_PROCESSO_CNJ, "PROCESSO_CNJ")
    entidades += extrair_por_regex(
        texto,
        REGEX_CPF,
        "CPF",
        validar=validar_cpf,
        mascarar=mascarar_dados_sensiveis
    )
    entidades += extrair_por_regex(texto, REGEX_CNPJ, "CNPJ")
    entidades += extrair_por_regex(texto, REGEX_OAB, "OAB")

    # Classe e assunto por linha
    entidades += extrair_linhas_chave(texto, REGEX_CLASSE_LINHA, "CLASSE")
    entidades += extrair_linhas_chave(texto, REGEX_ASSUNTO_LINHA, "ASSUNTO")

    # Classe e assunto por termos conhecidos
    entidades += extrair_lista_termos(texto, CLASSES_CONHECIDAS, "CLASSE")
    entidades += extrair_lista_termos(texto, ASSUNTOS_CONHECIDOS, "ASSUNTO")

    # Partes
    entidades += extrair_partes(texto)

    # Comarca e Vara
    entidades += extrair_por_regex(texto, REGEX_COMARCA, "COMARCA")
    entidades += extrair_por_regex(texto, REGEX_VARA, "VARA")

    # spaCy para nomes, órgãos, locais etc.
    entidades += extrair_spacy(texto)

    entidades = remover_duplicados(entidades)
    entidades = associar_entidades_ao_processo(entidades)

    return entidades


# =========================
# 5. Exemplo de uso
# =========================

if __name__ == "__main__":
    
    df1 = pd.read_parquet(
        r"C:\Users\lfmelo\Documents\Github\TJGO_Projeto-Processos-Pessoas-Vulneraveis\data\dataset_enriquecido_10062026_lematizado.parquet"
    )

    df = df1.reset_index().rename(columns={"index": "id"})

    df = df.head(1000).copy()

    entidades_lista = []

    for _, row in tqdm(df.iterrows(), total=len(df)):
        texto = row["inteiro_teor_lematizado"]
        id_processo = row["id"]

        ents = extrair_entidades_juridicas(texto, mascarar_dados_sensiveis=False)

        for e in ents:
            e["id_processo"] = id_processo

        entidades_lista.extend(ents)

    df_ents = pd.DataFrame(entidades_lista)

    df_ents.to_parquet(r"C:\Users\lfmelo\Documents\Github\TJGO_Projeto-Processos-Pessoas-Vulneraveis\data\entidades_extracao.parquet", index=False)