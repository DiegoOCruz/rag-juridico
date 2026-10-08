import re
from bs4 import BeautifulSoup

PADRAO_ARTIGO = re.compile(r"^Art\.\s*(\d+(?:-[A-Z])?)")

with open("dados/cdc.htm", encoding="windows-1252") as f:
    soup = BeautifulSoup(f, "html.parser")

textos = [re.sub(r"\s+", " ", p.get_text()).strip() for p in soup.find_all("p")]

numeros = []
for texto in textos:
    encontrado = PADRAO_ARTIGO.match(texto)
    if encontrado:
        numeros.append(encontrado.group(1))

print(len(numeros))
print(numeros)

