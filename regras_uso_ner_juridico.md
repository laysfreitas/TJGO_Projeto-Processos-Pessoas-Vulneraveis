# Regras de Uso do NER Jurídico

## 1. Objetivo

Este documento descreve as regras de uso do extrator de entidades nomeadas aplicado a textos jurídicos, especialmente petições, processos, movimentações e documentos relacionados a pessoas vulneráveis.

O objetivo do NER jurídico é identificar e estruturar informações que permitam vincular pessoas, partes, assuntos, classes processuais e dados processuais a um processo judicial.

O extrator deve ser usado como uma solução híbrida, combinando:

- **Regex** para entidades com formato fixo;
- **Listas de termos controlados** para classe e assunto;
- **spaCy NER** para pessoas, órgãos, locais e instituições;
- **Regras contextuais** para vincular entidades ao processo correto.

---

## 2. Entidades que devem ser extraídas

### 2.1 Entidades identificadoras

| Entidade | Descrição | Técnica recomendada |
|---|---|---|
| `PROCESSO_CNJ` | Número do processo no padrão CNJ | Regex |
| `CPF` | CPF de pessoa física | Regex + validação |
| `CNPJ` | CNPJ de pessoa jurídica | Regex |
| `OAB` | Número de inscrição de advogado | Regex |

### 2.2 Entidades processuais

| Entidade | Descrição | Técnica recomendada |
|---|---|---|
| `CLASSE` | Classe processual, como Procedimento Comum Cível, Mandado de Segurança etc. | Regex por linha + lista controlada |
| `ASSUNTO` | Assunto processual, como Saúde, Idoso, Pessoa com Deficiência etc. | Regex por linha + lista controlada |
| `COMARCA` | Comarca do processo | Regex + spaCy |
| `VARA` | Vara judicial vinculada ao processo | Regex |
| `ORGAO_OU_INSTITUICAO` | Tribunal, Ministério Público, Defensoria, Estado, Município etc. | spaCy + regras |

### 2.3 Entidades de pessoas e partes

| Entidade | Descrição | Técnica recomendada |
|---|---|---|
| `PESSOA` | Nome de pessoa identificado pelo modelo spaCy | spaCy NER |
| `AUTOR` | Autor, autora, requerente, exequente ou impetrante | Regex contextual |
| `REU` | Réu, ré, requerido, executado ou impetrado | Regex contextual |
| `ADVOGADO` | Advogado, advogada, procurador ou procuradora | Regex contextual |

---

## 3. Quando usar Regex, spaCy ou listas de termos

### 3.1 Usar Regex quando a entidade possui formato previsível

Use regex para:

- CPF;
- CNPJ;
- Número de processo CNJ;
- OAB;
- Vara;
- Campos estruturados como `Classe:` e `Assunto:`.

Exemplo:

```text
Processo: 1234567-89.2024.8.09.0051
CPF: 123.456.789-09
Classe: Procedimento Comum Cível
Assunto: Fornecimento de Medicamento
```

Essas entidades não devem depender exclusivamente do spaCy, pois o formato fixo permite extração mais precisa com regex.

---

### 3.2 Usar spaCy quando a entidade é textual e variável

Use spaCy para:

- nomes de pessoas;
- órgãos;
- instituições;
- localidades;
- expressões textuais não padronizadas.

Exemplo:

```text
João da Silva ajuizou ação contra o Estado de Goiás na Comarca de Goiânia.
```

Possíveis entidades:

| Texto | Entidade |
|---|---|
| João da Silva | `PESSOA` |
| Estado de Goiás | `ORGAO_OU_INSTITUICAO` |
| Goiânia | `LOCAL` |

---

### 3.3 Usar listas de termos para classe e assunto

Use listas controladas para identificar termos jurídicos e temas relevantes.

Exemplo de classes:

```python
CLASSES_CONHECIDAS = [
    "procedimento comum cível",
    "mandado de segurança",
    "execução fiscal",
    "cumprimento de sentença",
    "ação civil pública"
]
```

Exemplo de assuntos:

```python
ASSUNTOS_CONHECIDOS = [
    "idoso",
    "pessoa com deficiência",
    "criança e adolescente",
    "saúde",
    "fornecimento de medicamento",
    "internação",
    "violência doméstica",
    "curatela",
    "interdição",
    "bpc"
]
```

Essas listas devem ser revisadas e ampliadas conforme os textos analisados.

---

## 4. Regras de vinculação ao processo

Toda entidade extraída deve, sempre que possível, ser vinculada a um número de processo.

### 4.1 Regra principal

Quando o texto possuir um único número de processo, todas as entidades extraídas devem ser associadas a esse processo.

Exemplo:

```text
Processo: 1234567-89.2024.8.09.0051
Autor: João da Silva
Assunto: Pessoa com deficiência
```

Saída esperada:

| processo_vinculado | entidade | tipo |
|---|---|---|
| 1234567-89.2024.8.09.0051 | João da Silva | `AUTOR` |
| 1234567-89.2024.8.09.0051 | Pessoa com deficiência | `ASSUNTO` |

---

### 4.2 Regra para múltiplos processos no mesmo texto

Quando houver mais de um número de processo no mesmo documento, a entidade deve ser vinculada ao processo mais próximo no texto.

Critério recomendado:

```text
processo_vinculado = número de processo com menor distância textual da entidade
```

Essa regra é útil em documentos que mencionam processos relacionados, conexos ou incidentais.

---

### 4.3 Regra para ausência de processo

Quando nenhum número de processo for encontrado, o campo `processo_vinculado` deve receber `None` ou valor nulo.

Exemplo:

```json
{
  "label": "PESSOA",
  "texto": "João da Silva",
  "processo_vinculado": null
}
```

---

## 5. Regras específicas por entidade

## 5.1 CPF

### Técnica

- Usar regex para localizar CPFs com ou sem pontuação;
- Validar os dígitos verificadores;
- Remover CPFs inválidos;
- Opcionalmente mascarar o CPF na saída analítica.

### Formatos aceitos

```text
123.456.789-09
12345678909
```

### Regra de validação

O CPF deve:

- conter 11 dígitos;
- não ser sequência repetida, como `00000000000` ou `11111111111`;
- passar na validação dos dígitos verificadores.

### Regra de privacidade

Em bases analíticas, relatórios, dashboards ou arquivos compartilháveis, o CPF deve ser mascarado.

Formato recomendado:

```text
123.***.***-09
```

---

## 5.2 Número do processo CNJ

### Técnica

Usar regex.

### Formato esperado

```text
NNNNNNN-DD.AAAA.J.TR.OOOO
```

Exemplo:

```text
1234567-89.2024.8.09.0051
```

### Regex recomendada

```python
REGEX_PROCESSO_CNJ = r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b"
```

---

## 5.3 Classe processual

### Técnica

Usar duas estratégias combinadas:

1. Extração por linha estruturada;
2. Busca por termos conhecidos.

### Exemplos de linhas estruturadas

```text
Classe: Procedimento Comum Cível
Classe Processual: Mandado de Segurança
```

### Regex recomendada

```python
REGEX_CLASSE_LINHA = r"(?im)^\s*Classe(?:\s+Processual)?\s*[:\-]\s*(.+)$"
```

### Regra

Quando houver classe explícita em campo estruturado, essa informação deve ter prioridade sobre a classe encontrada por lista de termos.

---

## 5.4 Assunto

### Técnica

Usar duas estratégias combinadas:

1. Extração por linha estruturada;
2. Busca por termos conhecidos.

### Exemplos de linhas estruturadas

```text
Assunto: Pessoa com deficiência / Fornecimento de medicamento
Assuntos: Saúde, Internação, Idoso
```

### Regex recomendada

```python
REGEX_ASSUNTO_LINHA = r"(?im)^\s*Assunto(?:s)?\s*[:\-]\s*(.+)$"
```

### Regra

Um processo pode possuir múltiplos assuntos. Portanto, o campo `ASSUNTO` deve permitir múltiplos valores.

Exemplo:

```json
[
  {
    "label": "ASSUNTO",
    "texto": "Pessoa com deficiência"
  },
  {
    "label": "ASSUNTO",
    "texto": "Fornecimento de medicamento"
  }
]
```

---

## 5.5 Partes do processo

### Técnica

Usar regex contextual por rótulo textual.

### Termos equivalentes

| Entidade final | Termos equivalentes |
|---|---|
| `AUTOR` | Autor, Autora, Requerente, Exequente, Impetrante |
| `REU` | Réu, Ré, Requerido, Requerida, Executado, Executada, Impetrado, Impetrada |
| `ADVOGADO` | Advogado, Advogada, Procurador, Procuradora |

### Exemplos

```text
Autor: João da Silva
Requerente: Maria Oliveira
Réu: Estado de Goiás
Advogado: Pedro Santos - OAB/GO nº 12345
```

### Regra

O valor extraído deve ser o conteúdo após `:` ou `-`, removendo espaços excedentes.

---

## 5.6 OAB

### Técnica

Usar regex.

### Formatos aceitos

```text
OAB/GO nº 12345
OAB GO 12345
OAB nº 12345/GO
```

### Regra

A OAB deve ser vinculada preferencialmente ao advogado mais próximo no texto.

---

## 5.7 Órgãos, instituições e locais

### Técnica

Usar spaCy e regras complementares.

### Exemplos de instituições

```text
Estado de Goiás
Município de Goiânia
Ministério Público do Estado de Goiás
Defensoria Pública
Tribunal de Justiça do Estado de Goiás
```

### Regra

Entidades identificadas pelo spaCy como `ORG` devem ser convertidas para `ORGAO_OU_INSTITUICAO`.

Entidades identificadas como `LOC` devem ser convertidas para `LOCAL`.

---

## 6. Formato recomendado de saída

Cada entidade extraída deve ser representada como um registro independente.

### Campos mínimos

| Campo | Descrição |
|---|---|
| `label` | Tipo da entidade |
| `texto` | Texto extraído |
| `inicio` | Posição inicial da entidade no texto |
| `fim` | Posição final da entidade no texto |
| `origem` | Técnica usada para extração |
| `processo_vinculado` | Processo associado à entidade |

### Exemplo em JSON

```json
{
  "label": "ASSUNTO",
  "texto": "Pessoa com deficiência",
  "inicio": 120,
  "fim": 143,
  "origem": "regex_linha",
  "processo_vinculado": "1234567-89.2024.8.09.0051"
}
```

### Exemplo em tabela

| processo_vinculado | label | texto | origem |
|---|---|---|---|
| 1234567-89.2024.8.09.0051 | `AUTOR` | João da Silva | regex_partes |
| 1234567-89.2024.8.09.0051 | `CPF` | 123.***.***-09 | regex |
| 1234567-89.2024.8.09.0051 | `CLASSE` | Procedimento Comum Cível | regex_linha |
| 1234567-89.2024.8.09.0051 | `ASSUNTO` | Pessoa com deficiência | lista_termos |

---

## 7. Regras de deduplicação

Após a extração, entidades duplicadas devem ser removidas.

### Critério recomendado de duplicidade

Uma entidade é considerada duplicada quando possui a mesma combinação de:

- `label`;
- `texto` normalizado em minúsculas;
- `inicio`;
- `fim`.

Exemplo de chave:

```python
chave = (
    ent.get("label"),
    ent.get("texto", "").lower(),
    ent.get("inicio"),
    ent.get("fim")
)
```

---

## 8. Regras de privacidade e segurança

Como os textos jurídicos podem conter dados pessoais, o uso do extrator deve seguir cuidados mínimos de privacidade.

### 8.1 Dados sensíveis

Devem ser tratados com cuidado:

- CPF;
- nome completo;
- endereço;
- dados de saúde;
- informações sobre deficiência;
- dados de criança e adolescente;
- violência doméstica;
- dados familiares;
- números de documentos.

### 8.2 Arquivos internos e analíticos

Recomenda-se gerar duas versões de saída:

| Arquivo | Descrição |
|---|---|
| Saída completa | Uso interno e restrito, contendo CPF completo |
| Saída anonimizada | Uso analítico, contendo CPF mascarado |

### 8.3 Regra de compartilhamento

Nunca compartilhar bases com CPF completo, nomes completos e dados sensíveis sem autorização e sem necessidade técnica clara.

Para relatórios, dashboards e análises estatísticas, preferir dados anonimizados ou agregados.

---

## 9. Exemplo de uso no Python

```python
from extracao_ner import extrair_entidades_juridicas
import pandas as pd

texto = """
Processo: 1234567-89.2024.8.09.0051
Classe: Procedimento Comum Cível
Assunto: Fornecimento de medicamento / Pessoa com deficiência
Autor: João da Silva
CPF: 123.456.789-09
Réu: Estado de Goiás
Advogado: Maria Oliveira - OAB/GO nº 12345
Comarca de Goiânia
2ª Vara da Fazenda Pública Estadual
"""

entidades = extrair_entidades_juridicas(
    texto,
    mascarar_dados_sensiveis=True
)

df_entidades = pd.DataFrame(entidades)

print(df_entidades)
```

---

## 10. Exemplo de salvamento em CSV

```python
df_entidades.to_csv(
    "entidades_extraidas.csv",
    index=False,
    sep=";",
    encoding="utf-8-sig"
)
```

---

## 11. Exemplo de salvamento em Parquet

```python
df_entidades.to_parquet(
    "entidades_extraidas.parquet",
    index=False
)
```

Para salvar em Parquet, pode ser necessário instalar uma engine:

```powershell
python -m pip install pyarrow
```

---

## 12. Boas práticas de uso

1. Usar regex para entidades estruturadas.
2. Usar spaCy para nomes, instituições e locais.
3. Validar CPF antes de aceitar a entidade.
4. Mascarar CPF em saídas analíticas.
5. Permitir múltiplos assuntos por processo.
6. Sempre tentar vincular entidades ao processo CNJ mais próximo.
7. Revisar periodicamente as listas de classes e assuntos.
8. Manter logs de erros e textos não reconhecidos.
9. Não confiar 100% no NER automático sem validação amostral.
10. Avaliar precisão, revocação e falsos positivos em amostras reais.

---

## 13. Limitações conhecidas

O extrator pode apresentar erros nos seguintes casos:

- documentos digitalizados com OCR ruim;
- ausência de campos estruturados;
- nomes de pessoas escritos em caixa alta sem contexto;
- múltiplos processos no mesmo documento;
- assunto mencionado de forma indireta;
- classe processual abreviada;
- partes descritas em texto corrido;
- CPF inválido ou parcialmente oculto;
- órgãos públicos identificados incorretamente como pessoas pelo spaCy.

Por isso, o resultado deve ser considerado uma extração automática sujeita a revisão.

---

## 14. Erros comuns e correções

### 14.1 Erro: `ner already exists in pipeline`

Causa:

O modelo carregado já possui o componente `ner`.

Código errado:

```python
ner = nlp.add_pipe("ner")
```

Código correto:

```python
ner = nlp.get_pipe("ner")
```

Ou de forma segura:

```python
if "ner" in nlp.pipe_names:
    ner = nlp.get_pipe("ner")
else:
    ner = nlp.add_pipe("ner")
```

---

### 14.2 Erro: `ModuleNotFoundError: No module named 'click'`

Causa:

Instalação incompleta do spaCy ou ambiente virtual corrompido.

Correção:

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install --upgrade --force-reinstall click spacy
```

Se continuar, recriar a `.venv`:

```powershell
deactivate
Remove-Item -Recurse -Force .venv
py -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install spacy
python -m spacy download pt_core_news_md
```

---

## 15. Estrutura recomendada de projeto

```text
TJGO_Projeto-Processos-Pessoas-Vulneraveis/
│
├── NER/
│   ├── extracao_ner.py
│   ├── regras_uso_ner_juridico.md
│   └── saidas/
│       ├── entidades_extraidas.csv
│       └── entidades_extraidas_anonimizado.csv
│
├── data/
│   ├── entrada/
│   └── saida/
│
└── .venv/
```

---

## 16. Fluxo recomendado

```text
1. Ler texto bruto da petição/processo
2. Limpar espaços, quebras e caracteres especiais
3. Extrair PROCESSO_CNJ, CPF, CNPJ e OAB com regex
4. Extrair CLASSE e ASSUNTO por campos estruturados
5. Extrair CLASSE e ASSUNTO por listas de termos conhecidos
6. Extrair partes por regex contextual
7. Rodar spaCy para PESSOA, ORGAO_OU_INSTITUICAO e LOCAL
8. Remover duplicados
9. Vincular entidades ao processo mais próximo
10. Gerar DataFrame
11. Salvar saída completa e/ou anonimizada
```

---

## 17. Evoluções futuras recomendadas

1. Criar dicionário oficial de classes processuais.
2. Criar dicionário oficial de assuntos processuais.
3. Adicionar validação de CNPJ.
4. Criar regra para vincular OAB ao advogado mais próximo.
5. Criar regra para separar múltiplos assuntos em uma mesma linha.
6. Criar avaliação manual com amostra anotada.
7. Medir precisão, revocação e F1 por entidade.
8. Treinar um modelo NER customizado para entidades jurídicas específicas.
9. Integrar o extrator com pipeline de classificação de temas.
10. Salvar entidades em tabela relacional ou grafo para análise de vínculos.

---

## 18. Resumo das entidades finais

```text
PROCESSO_CNJ
CPF
CNPJ
OAB
CLASSE
ASSUNTO
PESSOA
AUTOR
REU
ADVOGADO
COMARCA
VARA
ORGAO_OU_INSTITUICAO
LOCAL
MISC
```

---

## 19. Recomendação principal

Para este projeto, não utilizar apenas NER estatístico.

A melhor estratégia é manter o modelo híbrido:

```text
Regex + listas controladas + spaCy + regras de associação
```

Essa abordagem tende a ser mais robusta para textos jurídicos, pois combina precisão em campos estruturados com flexibilidade para reconhecer nomes, órgãos e locais em texto livre.
