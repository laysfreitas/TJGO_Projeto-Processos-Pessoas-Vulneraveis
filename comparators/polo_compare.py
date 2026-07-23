"""Busca reversa: o nome cadastrado de um polo aparece no inteiro teor?"""
import re
import unicodedata


# Tokens que, no início de um campo de polo, indicam que o conteúdo é texto
# vazado de outra coluna (CSV upstream com aspas mal-escapadas) e não um
# nome de parte. Lista conservadora — usada só para flagar cadastro inválido.
_PREPOSICOES_INICIO = re.compile(
    r'^(?:no|na|nos|nas|sob|para|com|por|em|de|do|da|dos|das|que|se|ao|aos|à|às'
    r'|caput|nesta|nestes|nesse|nesses|nessa|nessas|esta|estes|este|aquela'
    r'|cujo|cuja|onde|sobre|entre|conforme|segundo|nos\s+termos|art|inciso)'
    r'\b',
    re.IGNORECASE,
)


def normalize_for_match(s: str) -> str:
    """Normaliza para comparação: remove acento, pontuação e caixa."""
    if not s:
        return ""
    s = unicodedata.normalize('NFKD', str(s)).encode('ASCII', 'ignore').decode('ASCII')
    s = re.sub(r'[^a-zA-Z0-9\s]', '', s)
    return re.sub(r'\s+', ' ', s.lower().strip())


def is_polo_invalido(s) -> bool:
    """Detecta cadastro de polo com texto vazado/lixo (não é nome de parte).

    Cobre os padrões observados no dataset 07/05/2026:
    - Inicia com preposição/conectivo ("no", "sob", "para a citação...").
    - Letras isoladas por espaços ("I N S I G N E R E L A T O R").
    - Contém marca de valor monetário ("R$", "valor total").
    - Inicia com símbolo/pontuação não-nominal.
    - Primeiro token é puramente numérico (vazamento de CPF/CNPJ).
    """
    if not s:
        return False
    s_str = str(s).strip()
    if not s_str:
        return False

    # 1) inicia com preposição/conectivo (e a string toda tem >2 palavras)
    if _PREPOSICOES_INICIO.match(s_str) and len(s_str.split()) > 2:
        return True

    # 2) padrão "letra-espaço-letra-espaço" (5 ou mais letras isoladas em sequência)
    if re.match(r'^(?:\S\s){5,}', s_str):
        return True

    # 3) marca monetária no campo de polo
    if re.search(r'\bR\$|\bvalor\s+(?:total|da\s+causa)\b', s_str, re.IGNORECASE):
        return True

    # 4) inicia com símbolo/pontuação claramente não-nominal (inclui hífen,
    #    pois nomes legítimos não começam com '-').
    if re.match(r'^[$°§\-(){}\[\].,;:]', s_str):
        return True

    # 5) começa com dígito MAS o primeiro token é todo dígitos/pontuação
    #    (ex.: "12345.67 esta na causa" — vazamento). Aceita nomes legítimos
    #    como "99pay Instituição", "3M do Brasil", "7-Eleven" — o primeiro
    #    token nesses casos contém pelo menos uma letra.
    if s_str[0].isdigit():
        first_token = s_str.split()[0]
        if not re.search(r'[A-Za-zÀ-ÿ]', first_token):
            return True

    return False


def are_names_equivalent(name1: str, name2: str, is_cnpj: bool = False) -> bool:
    """Verifica se dois nomes de partes referem-se à mesma entidade.
    
    - Para Pessoa Física (is_cnpj = False): Somos extremamente rígidos. Só aceitamos
      se forem idênticos (após remover acentos e capitalização). Diferenças como
      remoção de preposições ('de', 'do') ou grafia diferente caem como DIVERGENTE.
      
    - Para Pessoa Jurídica (is_cnpj = True): Somos mais flexíveis, ignorando conectivos,
      sufixos societários, siglas ao final e pequenas variações gráficas.
    """
    if not name1 or not name2:
        return False
        
    n1 = normalize_for_match(name1)
    n2 = normalize_for_match(name2)
    
    if n1 == n2:
        return True
        
    # Se for Pessoa Física (CPF), qualquer diferença nominal é considerada divergência (Rigor máximo)
    if not is_cnpj:
        return False
        
    # Preposições/artigos/conectivos a desconsiderar
    ignore_words = {'de', 'do', 'da', 'dos', 'das', 'e', 'o', 'a', 'em'}
    
    # Sufixos societários a desconsiderar
    corporate_suffixes = {'ltda', 'sa', 'eireli', 'me', 'epp', 'autarquia', 'federal', 'publica'}
    
    def clean_name(n: str) -> str:
        words = n.split()
        cleaned = [w for w in words if w not in ignore_words and w not in corporate_suffixes]
        return " ".join(cleaned)
        
    c1 = clean_name(n1)
    c2 = clean_name(n2)
    
    if c1 == c2:
        return True
        
    # Trata remoção de siglas/abreviações ao final (ex: 'INSS', 'CEF')
    w1 = c1.split()
    w2 = c2.split()
    if w1 and w2:
        if len(w1[-1]) <= 5 and " ".join(w1[:-1]) == " ".join(w2):
            return True
        if len(w2[-1]) <= 5 and " ".join(w2[:-1]) == " ".join(w1):
            return True
            
    # Comparação por distância de Levenshtein (RapidFuzz Ratio) nos nomes limpos
    try:
        from rapidfuzz import fuzz
        score = fuzz.ratio(c1, c2)
        if score >= 92:
            return True
    except ImportError:
        pass
        
    return False

def extracao_data(peticao):
    padrao = r"nascid\w+ em\s+(\d{1,2}[-/. ]\d{1,2}[-/. ]\d{4})"
    padrao2 = r"nascid\w+\s+(\d{1,2}[-/. ]\d{1,2}[-/. ]\d{4})"
    padrao3 = (
        r"\bnascid(?:o|a|os|as)\s+em\s+"
        r"(\d{1,2}\s+de\s+"
        r"(?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|"
        r"setembro|outubro|novembro|dezembro)"
        r"\s+de\s+\d{4})"
    )
    padrao4 = (
        r"nascer\s+na\s+data\s+"
        r"(\d{1,2}\s+de\s+"
        r"(?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|"
        r"setembro|outubro|novembro|dezembro)"
        r"\s+de\s+\d{4})"
    )
    datas = []
    # Busca todas as ocorrências no texto
    for match in re.finditer(padrao, peticao, re.IGNORECASE):
        # match.group(1) captura apenas o que está dentro dos parênteses (a data)
        data = match.group(1)
        datas.append(data)
        #print(f"Data 1 encontrada: {data} (na posição {match.start(1)})")

    for match in re.finditer(padrao2, peticao, re.IGNORECASE):
        data = match.group(1)
        datas.append(data)
        #print(f"Data 2 encontrada: {data} (na posição {match.start(1)})")

    for match in re.finditer(padrao3, peticao, re.IGNORECASE):
        data = match.group(1)
        datas.append(data)
        #print(f"Data 3 encontrada: {data} (na posição {match.start(1)})")

    for match in re.finditer(padrao4, peticao, re.IGNORECASE):
        data = match.group(1)
        datas.append(data)
        #print(f"Data 4 encontrada: {data} (na posição {match.start(1)})")
    
    return datas

def extracao_residencia(peticao):
    """
    Extrai endereços de residência de um texto de petição.
    """
    siglas_estados = r"(?:AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)"

    # Exige Cidade/UF sem espaço entre eles (ex: São Paulo/SP, Curitiba-PR)
    padrao = r"(?:residente|domiciliad\w+|residente e domiciliad\w+)(?:\s+em)?\s+(.+?\s+(?:CEP\s+\d{5}-\d{3}|[A-Za-zÀ-ÿ\s]+[,/]?[/|-]" + siglas_estados + r"))"    
    enderecos = []
    
    for match in re.finditer(padrao, peticao, re.IGNORECASE):
        # match.group(1) contém EXATAMENTE o endereço capturado pelo (.+?)
        endereco = match.group(1).strip()
        enderecos.append(endereco)
    
    return enderecos
    

def extract_name_preceding_doc(text: str, doc_raw: str) -> str:
    """Extrai o nome da parte que antecede seu respectivo CPF ou CNPJ na petição.
    
    Usado como mecanismo de resgate inteligente (rescue) quando o nome do polo
    cadastrado na capa (ex.: razão social 'Natasha Luiza Silveira Car Ltda')
    difere do nome grafado na petição (ex.: nome fantasia 'BRYAN CAR'), mas
    o documento cadastrado (CNPJ/CPF) bate perfeitamente.
    """
    # 1) Extrai os dígitos do documento
    doc_digits = re.sub(r'\D', '', str(doc_raw))
    if not doc_digits:
        return "", "", ""
    
    # 2) Cria uma regex flexível para encontrar o documento no texto, aceitando espaços e pontuações
    pattern_parts = [re.escape(d) for d in doc_digits]
    pattern_str = r'\b' + r'\s*[\.\/\-\s]*\s*'.join(pattern_parts) + r'\b'
    try:
        pattern = re.compile(pattern_str)
        match = pattern.search(text)
    except Exception:
        return "","", ""
        
    if not match:
        return "","", ""
    
    start_idx = match.start()
    end_idx = match.end()
    
    # 3) Pega a substring anterior ao documento (até 180 caracteres antes)
    sub = text[max(0, start_idx - 180):start_idx]

    # 3.1) Pega a substring posterior ao documento (até 180 caracteres depois)
    sub_pos = text[end_idx:min(end_idx + 450, len(text))]
    
    # 4) Encontra delimitadores comuns que separam o nome das qualificações da parte
    separators = [
        r',?\s*pessoa\s+jurídica',
        r',?\s*pessoa\s+física',
        r',?\s*brasileir[oa]',
        r',?\s*inscrit[oa]',
        r',?\s*portador[aa]',
        r',?\s*com\s+sede',
        r',?\s*residente',
        r',?\s*domiciliad[oa]',
        r',?\s*autarquia\b',
        r',?\s*fundação\b',
        r',?\s*representad[oa]\b',
        r'\bsob\b',
        r'\bno\s+cnpj\b',
        r'\bno\s+cpf\b'
    ]
    
    # Encontra o primeiro separador que aparece na substring anterior
    first_sep_idx = len(sub)
    for sep in separators:
        sep_match = re.search(sep, sub, re.IGNORECASE)
        if sep_match:
            if sep_match.start() < first_sep_idx:
                first_sep_idx = sep_match.start()
                
    # Trunca a substring no primeiro separador encontrado
    sub_truncated = sub[:first_sep_idx].strip()
    
    # 5) Limpa a string da esquerda para a direita, pegando o nome que está mais próximo do fim.
    # Delimitadores de início de nome: quebras de linha, pontos finais, ponto e vírgula, marcadores de lista
    splitters = [
        r'\n',
        r';',
        r'(?<!\d)\.(?!\d)', # Ponto final (que não seja divisor de número/lista)
        r'\bem\s+face\s+d[eoa]s?\b',
        r'\bem\s+desfavor\s+d[eoa]s?\b',
        r'\bcontra\b',
        r'\bpropor\b',
        r'\bpropost[oa]\b',
        r'\bajuizad[oa]\b',
        r'\bpolo\s+passivo\b',
        r'\bpolo\s+ativo\b',
        # Cabeçalhos/preâmbulos processuais que antecedem o nome da parte e
        # vazam para o span (ex.: 'Página 1 de 7 AO JUIZADO ... COMARCA
        # GOIÂNIA/GO <NOME>'). São termos que nunca compõem nome de parte;
        # cortamos por eles e ficamos com o que vem DEPOIS. Cortar
        # 'Goiás'/'Goiânia/GO' aqui é seguro porque o rescue só roda quando a
        # busca por substring (etapa 1) já falhou — uma parte homônima
        # legítima ('Estado de Goiás') já teria casado antes.
        r'p[áa]gina\s+\d+\s+de\s+\d+',
        r'\bao\s+ju[íi]z[oa]\b',
        r'\bao\s+ju[íi]zado\b',
        r'\bexcelent[íi]ssim\w*',
        r'\bmerit[íi]ssim\w*',
        r'\bgoi[âa]nia\s*[-/]\s*go\b',
        r'\bcomarca\s+(?:de\s+)?goi[áa]s\b',
        r'\bestado\s+de\s+goi[áa]s\b',
        r'\bgoi[áa]s\b',
        r'\blei\s+n?[º°\.\s]*\d[\d\./]*',
        r'\btema\s+\d+',
        r'\b(?:stf|stj|tjgo|tj)\b',
        r'§',
        # Blocos de endereço/contato que antecedem litisconsortes ('..., e
        # AGÊNCIA ...'): cortamos no endereço para isolar o nome final.
        r'\bcep\b',
        r'\d{2}\.?\d{3}\s*-\s*\d{3}\b',  # número de CEP (ex.: 74.884-900)
        r'\bfone\b',
        r'\bpa[çc]o\s+municipal\b',
        r'\batrav[ée]s\s+d[eo]\b',
    ]
    
    # Faz split pelos splitters
    combined_splitter = '|'.join(f'(?:{s})' for s in splitters)
    segments = re.split(combined_splitter, sub_truncated, flags=re.IGNORECASE)
    
    # Pegamos o último segmento válido
    candidate = ""
    for seg in reversed(segments):
        seg_clean = seg.strip()
        # Remove marcadores de lista no início, ex: "1.", "3)", "a)"
        seg_clean = re.sub(r'^(?:\d+[\.\)\-]?|[a-zA-Z][\.\)\-]?)\s+', '', seg_clean)
        # Remove caracteres especiais residuais no início
        seg_clean = re.sub(r'^[^a-zA-ZÀ-ÿ0-9]+', '', seg_clean).strip()
        if len(seg_clean) >= 3:
            candidate = seg_clean
            break

    # 6) Tenta extrair a data de nascimento associada ao documento
    data_nascimento = extracao_data(sub)
    if data_nascimento:
        data_nascimento = data_nascimento[-1]  # Pega a última data encontrada, que é a mais próxima do documento
    else:
        data_nascimento = ""
    
    residente = extracao_residencia(sub_pos)
    if residente:
        residente = residente[0]  # Pega o primeiro endereço encontrado, que é o mais próximo do documento
    else:
        residente = ""

    return candidate, data_nascimento, residente

def polo_reverse_search(texto_doc: str, alvo_meta: str, documentos_meta: str = None) -> tuple[bool, list[dict]]:
    """Verifica se TODOS os polos cadastrados aparecem no texto da petição.

    Trata `#` como separador de litisconsórcio: o cadastro pode trazer N
    polos (`'Empresa A#Empresa B'`) e o match só é positivo quando todos
    os N aparecem no texto. Partes com menos de 3 caracteres são ignoradas.

    Retorna (achou, items):
      - achou: True se todas as partes válidas baterem (substring exata ou resgatada via CPF/CNPJ).
      - items: lista de dicts na ordem original do cadastro, cada um com:
            {"value": str, "found": bool, "matched_text": str}
        - `value`: nome cadastrado (texto da capa).
        - `found`: True se a substring normalizada do cadastro está no texto ou
                   se foi resgatada via documento (CPF/CNPJ) correspondente.
        - `matched_text`: texto a exibir na coluna 'Extraído da Petição':
            • `value` quando `found=True` (a petição contém literalmente);
            • nome resgatado da petição quando encontrado via documento;
            • span fuzzy do petição quando `found=False` mas RapidFuzz acha
              uma janela contígua acima do limiar (truncamento, ortografia);
            • `""` quando nem substring nem fuzzy encontram nada útil.
    """
    if not alvo_meta:
        return False, []

    s = str(alvo_meta).strip()
    if not s:
        return False, []

    partes_raw = s.split('#')
    docs_raw = str(documentos_meta).split('#') if documentos_meta else []

    # Import tardio — só pagamos o custo de carregar o RapidFuzz quando há
    # de fato divergência por substring.
    _find_fuzzy_span = None

    doc_norm = normalize_for_match(texto_doc)
    items: list[dict] = []
    tem_faltante = False
    tem_valido = False
    
    for idx, parte_raw in enumerate(partes_raw):
        parte = parte_raw.strip()
        if len(parte) < 3:
            continue
        meta_norm = normalize_for_match(parte)
        if not meta_norm:
            continue
        tem_valido = True
        
        # 1) Busca exata substring
        found = meta_norm in doc_norm
        matched_text = parte if found else ""
        
        # 2) Resgate inteligente via documento correspondente (CPF/CNPJ)
        if not found and idx < len(docs_raw):
            doc_candidate = docs_raw[idx].strip()
            if doc_candidate:
                doc_digits = re.sub(r'\D', '', doc_candidate)
                if len(doc_digits) >= 8:
                    # Verifica se o documento está no texto da petição
                    pattern_parts = [re.escape(d) for d in doc_digits]
                    pattern_str = r'\b' + r'\s*[\.\/\-\s]*\s*'.join(pattern_parts) + r'\b'
                    try:
                        pattern = re.compile(pattern_str)
                        doc_match = pattern.search(texto_doc)
                    except Exception:
                        doc_match = None
                        
                    if doc_match:
                        # O documento está na petição! Vamos tentar resgatar o nome que o antecede.
                        rescued_name = extract_name_preceding_doc(texto_doc, doc_digits)
                        if rescued_name:
                            # Determina se o documento correspondente é um CNPJ (PJ) ou CPF (PF)
                            doc_padded = doc_digits.zfill(11) if len(doc_digits) <= 11 else doc_digits.zfill(14)
                            is_cnpj = len(doc_padded) == 14
                            # Se os nomes forem equivalentes (ex.: siglas, pequenas variações), assume conforme (found=True).
                            # Caso contrário, mantém found=False para sinalizar divergência relevante (ex.: razão vs fantasia).
                            found = are_names_equivalent(parte, rescued_name, is_cnpj=is_cnpj)
                            matched_text = rescued_name
                            
        # 3) Busca fuzzy via RapidFuzz se ainda não foi encontrado
        if not found:
            tem_faltante = True
            if not matched_text:  # Só busca fuzzy se não foi preenchido pelo resgate inteligente
                if _find_fuzzy_span is None:
                    try:
                        from extractors.polo_extractor import find_best_polo_span as _f
                    except ImportError:
                        try:
                            from extractors.polo_extractor import find_best_polo_span as _f
                        except ImportError:
                            _f = lambda *_args, **_kw: None  # noqa: E731
                    _find_fuzzy_span = _f
                span = _find_fuzzy_span(texto_doc, parte)
                if span:
                    matched_text = span
                
        items.append({
            "value": parte,
            "found": found,
            "matched_text": matched_text,
        })

    ok = tem_valido and not tem_faltante
    return ok, items
