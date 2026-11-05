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
PADRAO_PARAGRAFO = re.compile(r"^§\s*(\d+)[º°]?", re.IGNORECASE)
PADRAO_INCISO = re.compile(r"^([IVXLCDM]+)\s+-")


def montar_texto(art, nome_lei):
    hierarquia = [n for n in (art["titulo"], art["capitulo"], art["secao"]) if n]
    return "\n".join([nome_lei] + hierarquia + art["dispositivos"])

def localizar_incisos(art):
    caput = art["dispositivos"][0]

    contexto_pai = caput
    referencia_pai = None
    incisos = []

    for dispositivo in art["dispositivos"][1:]:
        paragrafo = PADRAO_PARAGRAFO.match(dispositivo)

        if paragrafo:
            referencia_pai = f"§{paragrafo.group(1)}"
            contexto_pai = dispositivo
            continue

        inciso = PADRAO_INCISO.match(dispositivo)

        if inciso:
            numero_inciso = inciso.group(1)

            if referencia_pai:
                referencia = f"{referencia_pai}-{numero_inciso}"
            else:
                referencia = numero_inciso

            incisos.append(
                {
                    "referencia": referencia,
                    "contexto_pai": contexto_pai,
                    "texto": dispositivo,
                }
            )

    return incisos

def montar_chunk_inciso(art, inciso):
    caput = art["dispositivos"][0]

    dispositivos_do_chunk = [caput]

    if inciso["contexto_pai"] != caput:
        dispositivos_do_chunk.append(inciso["contexto_pai"])

    dispositivos_do_chunk.append(inciso["texto"])

    art_do_chunk = {
        **art,
        "dispositivos": dispositivos_do_chunk,
    }

    return {
        "id_chunk": f"{art['numero']}-{inciso['referencia']}",
        "numero_art": art["numero"],
        "texto": montar_texto(art_do_chunk, NOME_LEI),
        "tipo": "inciso",
        "referencia": inciso["referencia"],
    }


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
            texto_limpo = PADRAO_ANOTACAO.sub("", d).strip()
            texto_limpo = re.sub(r"\s+Vigência$", "", texto_limpo, flags=re.IGNORECASE)
            texto_limpo = re.sub(
            r"^XI - Dispositivo incluído pela MPV nº 1\.890-67, de 22\.10\.1999, "
            r"transformado em inciso XIII, quando da conversão na Lei nº 9\.870, de 23\.11\.1999$",
            "",
            texto_limpo,
            flags=re.IGNORECASE,
        )
            if texto_limpo:
                dispositivos.append(texto_limpo)

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

    # for numero in ["4", "51"]:
    #     art = next(a for a in artigos if a["numero"] == numero)
    #     print(f"\n=== Art. {numero} ===")
    #     print("Anotações:", art["anotacoes"])
    #     for d in art["dispositivos"]:
    #         print("  -", d[:90])

    # print("\nArt. 11 ainda existe?", any(a["numero"] == "11" for a in artigos))
    
    # tamanhos = sorted(
    # ((len("\n".join(a["dispositivos"])), a["numero"]) for a in artigos),
    # reverse=True,
    # )
    # print("Mais longos:", tamanhos[:5])
    # print("Mais curtos:", tamanhos[-5:])
    
    # art17 = next(a for a in artigos if a["numero"] == "17")
    # print(montar_texto(art17, NOME_LEI))
    
    # print("\n=== Chunk do inciso I do art. 39 ===")
    # art39 = next(art for art in artigos if art["numero"] == "39")
    # chunk = montar_chunk_inciso(art39, "I")

    # print(chunk["id_chunk"])
    # print(chunk["texto"])
    # print('-' * 40)    
    # print("\n=== Chunk do inciso II do art. 39 ===")
    # art39 = next(art for art in artigos if art["numero"] == "39")
    # chunk = montar_chunk_inciso(art39, "II")

    # print(chunk["id_chunk"])
    # print(chunk["texto"])
    art12 = next(art for art in artigos if art["numero"] == "12")

    for inciso in localizar_incisos(art12):
        print(inciso["referencia"])
        print("  Pai:", inciso["contexto_pai"])
        print("  Texto:", inciso["texto"])
        inciso = next(
            inciso
        for inciso in localizar_incisos(art12)
        if inciso["referencia"] == "§3-I"
    )

    chunk = montar_chunk_inciso(art12, inciso)

    print("\n=== Chunk 12-§3-I ===")
    print(chunk["id_chunk"])
    print(chunk["texto"])