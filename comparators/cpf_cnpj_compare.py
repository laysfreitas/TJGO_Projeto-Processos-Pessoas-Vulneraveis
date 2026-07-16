"""Busca reversa: o CPF/CNPJ cadastrado aparece no inteiro teor?"""
import re


# Threshold mínimo de dígitos significativos por parte do cadastro.
# Abaixo disso (ex.: "191", "0") considera-se texto vazado, não documento.
_MIN_DIGITOS = 8


def _is_cpf_valido_dv(d: str) -> bool:
    """Valida CPF de 11 dígitos pelos dois dígitos verificadores."""
    if len(d) != 11 or len(set(d)) == 1:
        return False
    s = sum(int(d[i]) * (10 - i) for i in range(9)) % 11
    dv1 = 0 if s < 2 else 11 - s
    if dv1 != int(d[9]):
        return False
    s = sum(int(d[i]) * (11 - i) for i in range(10)) % 11
    dv2 = 0 if s < 2 else 11 - s
    return dv2 == int(d[10])


def _is_cnpj_valido_dv(d: str) -> bool:
    """Valida CNPJ de 14 dígitos pelos dois dígitos verificadores."""
    if len(d) != 14 or len(set(d)) == 1:
        return False
    pesos1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    pesos2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    s = sum(int(d[i]) * pesos1[i] for i in range(12)) % 11
    dv1 = 0 if s < 2 else 11 - s
    if dv1 != int(d[12]):
        return False
    s = sum(int(d[i]) * pesos2[i] for i in range(13)) % 11
    dv2 = 0 if s < 2 else 11 - s
    return dv2 == int(d[13])


def _parte_invalida(parte: str) -> bool:
    """Detecta se uma parte (CPF ou CNPJ único) é cadastralmente inválida.

    Critérios cumulativos:
    - contém letras → texto livre vazado;
    - dígitos significativos abaixo do mínimo → fragmento sem sentido;
    - mais de 14 dígitos → tamanho incompatível com CPF (11) ou CNPJ (14);
    - DV inválido após padding → número fabricado ou truncado errado.
    """
    if not parte:
        return False
    p = parte.strip()
    if not p:
        return False
    if re.search(r'[A-Za-zÀ-ÿ]', p):
        return True
    digits = re.sub(r'\D', '', p)
    if len(digits) < _MIN_DIGITOS or len(digits) > 14:
        return True
    padded = digits.zfill(11) if len(digits) <= 11 else digits.zfill(14)
    if len(padded) == 11:
        return not _is_cpf_valido_dv(padded)
    return not _is_cnpj_valido_dv(padded)


def pad_documento(s) -> str:
    """Restaura zeros à esquerda em CPF (11 dígitos) ou CNPJ (14 dígitos).

    Sistemas como Excel/Power BI tratam CPF/CNPJ como número e cortam o zero
    inicial — '04660066169' vira '4660066169'. Aqui padronizamos:
      - até 11 dígitos → CPF (zfill 11)
      - 12 a 14 dígitos → CNPJ (zfill 14)
      - acima ou inválido → devolve a string original
      - se a entrada contiver letras (texto livre vazado por CSV mal-formado),
        devolve a string original sem inventar dígitos a partir de números
        espalhados pelo texto.
    """
    if not s:
        return ""
    s_str = str(s).strip()
    if '#' in s_str:
        return '#'.join(pad_documento(p.strip()) for p in s_str.split('#') if p.strip())
    if re.search(r'[A-Za-zÀ-ÿ]', s_str):
        return s_str
    nums = re.sub(r'\D', '', s_str)
    if not nums or len(nums) > 14:
        return s_str
    if len(nums) <= 11:
        return nums.zfill(11)
    return nums.zfill(14)


def is_documento_invalido(s) -> bool:
    """Detecta cadastro de CPF/CNPJ que não é um documento válido.

    Para uso em gabinete jurídico (rigor). Qualquer parte separada por `#`
    que falhe em qualquer um dos critérios torna o cadastro inteiro inválido:

    - presença de letras (texto vazado);
    - menos de 8 dígitos significativos (ex.: '191', '0' — fragmentos);
    - mais de 14 dígitos (não cabe em CPF/CNPJ);
    - dígito verificador (DV) inválido após padronização de zeros à esquerda.

    A regra é estrita por design: cadastros suspeitos não podem ser aprovados
    automaticamente — devolve True para forçar revisão humana.
    """
    if not s:
        return False
    s_str = str(s).strip()
    if not s_str:
        return False
    partes = [p.strip() for p in s_str.split('#') if p.strip()]
    if not partes:
        return False
    return any(_parte_invalida(p) for p in partes)


def cpf_reverse_search(texto_doc: str, alvo_meta: str) -> tuple[bool, list[dict]]:
    """Verifica se TODOS os CPFs/CNPJs cadastrados aparecem no texto.

    Usa **forward extraction com validação de DV**: extrai todos os
    CPFs/CNPJs do texto via regex + DV, e checa pertinência exata em
    conjunto. Mais rigoroso que substring concatenando dígitos — elimina
    falsos positivos onde os dígitos cadastrados aparecem fragmentados
    dentro de outros números.

    Trata `#` como separador de litisconsórcio: cadastros com múltiplos
    documentos só batem quando TODOS os válidos estão presentes no texto.
    Partes inválidas (DV ruim, fragmentos, letras) são descartadas antes
    do match — o pipeline marca isso à parte via `is_documento_invalido`.

    Retorna (achou, items):
      - achou: True se todos os documentos válidos baterem.
      - items: lista de dicts `{"value": str, "found": bool}` na ordem
        original do cadastro, já normalizado pelo `pad_documento`.
    """
    if not alvo_meta:
        return False, []

    s = str(alvo_meta).strip()
    if not s:
        return False, []

    # Forward extraction — import tardio para evitar ciclo.
    try:
        from src.extractors.cpf_cnpj_extractor import extract_documents
    except ImportError:
        from extractors.cpf_cnpj_extractor import extract_documents
    extracted = extract_documents(str(texto_doc))

    items: list[dict] = []
    tem_faltante = False
    tem_valido = False
    for parte in s.split('#'):
        parte = parte.strip()
        if not parte:
            continue
        if _parte_invalida(parte):
            # Cadastro lixo (fragmento, letras, DV ruim). Não tenta matchar.
            continue
        alvo_padded = pad_documento(parte)
        meta_nums = re.sub(r'\D', '', alvo_padded)
        if len(meta_nums) < _MIN_DIGITOS:
            continue
        tem_valido = True
        if len(meta_nums) == 11:
            found = meta_nums in extracted['cpfs']
        elif len(meta_nums) == 14:
            found = meta_nums in extracted['cnpjs']
        else:
            found = False
        if not found:
            tem_faltante = True
        items.append({"value": alvo_padded, "found": found})

    ok = tem_valido and not tem_faltante
    return ok, items
