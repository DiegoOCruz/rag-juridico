import re
from bs4 import BeautifulSoup
from collections import Counter
    
PADRAO_ARTIGO = re.compile(r"^Art\.\s*(\d+(?:-[A-Z])?)")
PADRAO_TITULO = re.compile(r"^TÍTULO\s", re.IGNORECASE)
PADRAO_CAPITULO = re.compile(r"^CAPÍTULO\s", re.IGNORECASE)
PADRAO_SECAO = re.compile(r"^SEÇÃO\s", re.IGNORECASE)
PADRAO_ANOTACAO = re.compile(
    r"\s*\((?:Incluíd[oa]|Redação dada|Vigência)[^()]*\)", re.IGNORECASE
)
NOME_LEI = "Código de Defesa do Consumidor (Lei nº 8.078/1990)"


def montar_texto(art, nome_lei):
    hierarquia = [n for n in (art["titulo"], art["capitulo"], art["secao"]) if n]
    return "\n".join([nome_lei] + hierarquia + art["dispositivos"])


def ler_paragrafos(caminho):
    with open(caminho, encoding="windows-1252") as f:
        soup = BeautifulSoup(f, "html.parser")
    return [re.sub(r"\s+", " ", p.get_text()).strip() for p in soup.find_all("p")]

def agrupar_artigos(textos):
    artigos = []
    atual = None
    titulo = capitulo = secao = None
    dentro_da_lei = False

    for texto in textos:
        if not texto:
            continue

        if not dentro_da_lei:
            if PADRAO_TITULO.match(texto):
                dentro_da_lei = True
            else:
                continue

        if texto.startswith("Brasília"):
            break

        artigo = PADRAO_ARTIGO.match(texto)

        if PADRAO_TITULO.match(texto):
            titulo, capitulo, secao = texto, None, None
        elif PADRAO_CAPITULO.match(texto):
            capitulo, secao = texto, None
        elif PADRAO_SECAO.match(texto):
            secao = texto
        elif artigo:
            atual = {
                "numero": artigo.group(1),
                "titulo": titulo,
                "capitulo": capitulo,
                "secao": secao,
                "dispositivos": [texto],
            }
            artigos.append(atual)
        elif atual is not None:
            atual["dispositivos"].append(texto)

    return artigos

def limpar_artigos(artigos):
    resultado = []
    for art in artigos:
        dispositivos = []
        anotacoes = []

        for d in art["dispositivos"]:
            if "(vetado)" in d.lower():
                continue
            anotacoes += [a.strip(" ()") for a in PADRAO_ANOTACAO.findall(d)]
            dispositivos.append(PADRAO_ANOTACAO.sub("", d).strip())

        if not dispositivos:
            continue

        resultado.append({
            **art,
            "dispositivos": dispositivos,
            "anotacoes": list(dict.fromkeys(anotacoes)),
        })
    return resultado

if __name__ == "__main__":
    artigos = limpar_artigos(agrupar_artigos(ler_paragrafos("dados/cdc.htm")))
    print(len(artigos))

    for numero in ["4", "51"]:
        art = next(a for a in artigos if a["numero"] == numero)
        print(f"\n=== Art. {numero} ===")
        print("Anotações:", art["anotacoes"])
        for d in art["dispositivos"]:
            print("  -", d[:90])

    print("\nArt. 11 ainda existe?", any(a["numero"] == "11" for a in artigos))
    
    tamanhos = sorted(
    ((len("\n".join(a["dispositivos"])), a["numero"]) for a in artigos),
    reverse=True,
    )
    print("Mais longos:", tamanhos[:5])
    print("Mais curtos:", tamanhos[-5:])
    
    art17 = next(a for a in artigos if a["numero"] == "17")
    print(montar_texto(art17, NOME_LEI))