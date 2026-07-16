"""Extração de polos (nomes/razões sociais) da petição via fuzzy matching.

Quando o nome cadastrado não aparece literalmente no texto, tentamos encontrar
a melhor janela contígua com cobertura suficiente — útil para casos onde a
petição traz o nome truncado (ex.: '... & Frio Ltda' vs cadastro
'... & Frios Ltda') ou com pequenas variações ortográficas.

A classificação CONFORME/DIVERGENTE continua sendo decidida pelo `polo_compare`
(substring exata, rigor mantido). Este módulo só fornece o texto a exibir na
coluna 'Extraído da Petição Inicial' quando a substring exata não bate.
"""
from typing import Optional
import unicodedata

try:
    from rapidfuzz.fuzz import partial_ratio_alignment
    _RAPIDFUZZ_OK = True
except ImportError:
    _RAPIDFUZZ_OK = False


# Score mínimo (0-100) do RapidFuzz partial_ratio para considerar match.
# 85 captura truncamentos reais ('& Frio' vs '& Frios Ltda' → 99) e rejeita
# pares ruidosos que compartilham só tokens comuns ('LTDA', 'EMPRESA').
# Calibrado contra o lote 15/05/2026 — abaixar para 75 introduz falso
# positivo entre cadastros distintos da mesma classe.
DEFAULT_THRESHOLD = 85


def _build_search_index(text: str) -> tuple[str, list[int]]:
    """Constrói uma forma busca-amigável do texto preservando o mapeamento
    índice (forma de busca) → índice (texto original).

    A forma de busca é lowercase sem diacríticos. Não removemos pontuação
    para que os índices fiquem alinhados — só descartamos os combining marks
    introduzidos pelo NFKD.
    """
    chars: list[str] = []
    index_map: list[int] = []
    for i, ch in enumerate(text):
        for nch in unicodedata.normalize('NFKD', ch.lower()):
            if unicodedata.combining(nch):
                continue
            chars.append(nch)
            index_map.append(i)
    return ''.join(chars), index_map


def _to_search_form(s: str) -> str:
    """Mesma normalização do índice, mas sem mapeamento — para o target."""
    if not s:
        return ""
    nfkd = unicodedata.normalize('NFKD', s.lower())
    return ''.join(ch for ch in nfkd if not unicodedata.combining(ch))


def find_best_polo_span(
    text: str,
    target: str,
    threshold: int = DEFAULT_THRESHOLD,
) -> Optional[str]:
    """Procura no texto da petição a melhor janela contígua para `target`.

    Devolve a substring do texto **original** (case preservada) quando o
    score do `partial_ratio_alignment` >= `threshold`. Retorna None em caso
    de score abaixo do limiar, RapidFuzz indisponível, ou alvo muito curto.

    O alinhamento é feito sobre a forma lowercased+sem-diacríticos; o trecho
    devolvido é reconstruído via mapeamento de índices para o texto original.
    """
    if not _RAPIDFUZZ_OK or not text or not target:
        return None

    target_clean = target.strip()
    if len(target_clean) < 4:
        return None

    target_search = _to_search_form(target_clean)
    if not target_search:
        return None

    text_search, index_map = _build_search_index(text)
    if not text_search or not index_map:
        return None

    try:
        alignment = partial_ratio_alignment(target_search, text_search)
    except (TypeError, ValueError):
        return None

    if alignment is None or alignment.score < threshold:
        return None

    s_start = alignment.dest_start
    s_end = alignment.dest_end
    if s_start is None or s_end is None or s_end <= s_start:
        return None
    if s_end > len(index_map):
        s_end = len(index_map)
    if s_start >= len(index_map):
        return None

    orig_start = index_map[s_start]
    orig_end = index_map[s_end - 1] + 1

    # Expand span to include trailing acronyms/types (e.g. " - INSS", " (INSS)", " S/A", " LTDA - ME")
    import re
    expanded = True
    while expanded:
        expanded = False
        tail = text[orig_end:orig_end + 30]
        # Match acronyms like " - INSS" or " (INSS)"
        match_acronym = re.match(r'^(\s*[\-\–\—\/]\s*[A-ZÀ-Ú0-9]{2,10}\b|\s*\(\s*[A-ZÀ-Ú0-9]{2,10}\s*\))', tail)
        if match_acronym:
            orig_end += match_acronym.end()
            expanded = True
        else:
            # Match standard legal suffixes
            match_suffix = re.match(r'^(\s+(?:S/?[Aa]\.?|L[Tt][Dd][Aa]\.?|E[Ii][Rr][Ee][Ll][Ii]|M[Ee]|E[Pp][Pp])\b)', tail, re.IGNORECASE)
            if match_suffix:
                orig_end += match_suffix.end()
                expanded = True

    span = text[orig_start:orig_end].strip()
    if not span:
        return None

    # Proteção contra spans desproporcionalmente longos (alinhamento ruidoso).
    if len(span) > len(target_clean) * 2.5:
        return None

    return span
