r"""Extração direta (forward) de CPFs e CNPJs do texto da petição.

Estratégia:
1. Regex tolerante ao formato (com ou sem `.`, `/`, `-`).
2. `(?<!\d)`/`(?!\d)` em vez de `\b` para aceitar CPFs colados a letras
   (ex.: "CPF12345678901").
3. Validação de dígito verificador (DV) — só entram no resultado documentos
   matematicamente válidos. Filtra falsos positivos de 11/14 dígitos
   aleatórios (probabilidade ~1% de DV bater por acaso).
"""
import re

try:
    from src.comparators.cpf_cnpj_compare import _is_cpf_valido_dv, _is_cnpj_valido_dv
except ImportError:
    from comparators.cpf_cnpj_compare import _is_cpf_valido_dv, _is_cnpj_valido_dv


# CNPJ: 14 dígitos. Separadores (`.`, `/`, `-`, espaço) opcionais e
# REPETÍVEIS entre os grupos — PDFs jurídicos trazem pontuação duplicada/mista
# por erro de digitação/OCR (ex.: '0001-.89', '0001 -89'). O DV valida no fim,
# então tolerar separadores extras não introduz falso positivo relevante.
# Casa primeiro para não ser confundido com um CPF embutido.
_CNPJ_PATTERN = re.compile(
    r'(?<!\d)(\d{2}[.\-/\s]*\d{3}[.\-/\s]*\d{3}[.\-/\s]*\d{4}[.\-/\s]*\d{2})(?!\d)'
)

# CPF: 11 dígitos. Mesma tolerância a separadores repetidos/mistos
# (ex.: '880.571.191-.87' — hífen seguido de ponto).
_CPF_PATTERN = re.compile(
    r'(?<!\d)(\d{3}[.\-\s]*\d{3}[.\-\s]*\d{3}[.\-\s]*\d{2})(?!\d)'
)


def extract_documents(text: str) -> dict:
    """Extrai CPFs e CNPJs do texto, validados por DV.

    Args:
        text: petição inicial em texto plano (após `clean_text`).

    Returns:
        Dict `{'cpfs': set[str], 'cnpjs': set[str]}` com documentos em
        forma canônica (só dígitos, sem pontuação). Apenas DV válidos.
    """
    if not text:
        return {'cpfs': set(), 'cnpjs': set()}

    s = str(text)
    cpfs: set[str] = set()
    cnpjs: set[str] = set()

    # CNPJs primeiro — depois descobrimos as posições para não duplicar como CPF.
    cnpj_spans: list[tuple[int, int]] = []
    for m in _CNPJ_PATTERN.finditer(s):
        digits = re.sub(r'\D', '', m.group(1))
        if len(digits) == 14 and _is_cnpj_valido_dv(digits):
            cnpjs.add(digits)
            cnpj_spans.append(m.span())

    def _dentro_de_cnpj(pos: int) -> bool:
        for a, b in cnpj_spans:
            if a <= pos < b:
                return True
        return False

    for m in _CPF_PATTERN.finditer(s):
        if _dentro_de_cnpj(m.start()):
            continue
        digits = re.sub(r'\D', '', m.group(1))
        if len(digits) == 11 and _is_cpf_valido_dv(digits):
            cpfs.add(digits)

    return {'cpfs': cpfs, 'cnpjs': cnpjs}


def documento_presente(cadastro_digits: str, extracted: dict) -> bool:
    """Verifica se o documento cadastrado está no conjunto extraído.

    Args:
        cadastro_digits: dígitos do cadastro já normalizados (11 ou 14).
        extracted: dict retornado por `extract_documents`.

    Returns:
        True se `cadastro_digits` foi encontrado e validado por DV no texto.
    """
    if not cadastro_digits:
        return False
    if len(cadastro_digits) == 11:
        return cadastro_digits in extracted['cpfs']
    if len(cadastro_digits) == 14:
        return cadastro_digits in extracted['cnpjs']
    return False
