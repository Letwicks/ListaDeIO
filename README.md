# Lista de I/O

Gera uma planilha Excel com a lista de I/O de PLCs Rockwell/Allen-Bradley a partir
de arquivos `.L5X` (exportação Studio 5000), rastreando a estação de cada ponto de
I/O pelas rotinas de programa (RLL) que referenciam cada tag.

## Instalação

```
pip install -r requirements.txt
```

## Uso

```
python main.py
```

ou dê duplo clique em `run.bat`.

As instruções de uso completas estão dentro do próprio programa, na aba "Instruções".

## Executável (sem precisar instalar Python)

Já existe um executável pronto em `dist\ListaDeIO\ListaDeIO.exe` — basta dar duplo
clique. Não precisa de Python nem de instalar nenhuma dependência.

A distribuição é em **pasta** (não em arquivo único): `dist\ListaDeIO\` contém o
`.exe` e a subpasta `_internal` com as bibliotecas. É o mesmo formato usado no
FaltGenerate e nas outras ferramentas — reduz falso-positivo de antivírus, que
tende a desconfiar mais de um `.exe` único que se autoextrai. Para distribuir,
copie a pasta `ListaDeIO` inteira (não só o `.exe`).

Para gerar um novo executável depois de alterar o código:

```
pip install pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --name "ListaDeIO" --icon app.ico --distpath dist --workpath build --specpath . main.py
```

Se precisar regenerar o `app.ico` (ícone da barra de tarefas/Explorer), rode `python gerar_icone.py` antes.

O executável fica em `dist\ListaDeIO\ListaDeIO.exe`. A pasta `build\` só tem
arquivos temporários do processo de build e pode ser apagada.

## Estrutura

- `main.py` — ponto de entrada (GUI).
- `core/extractor.py` — leitura em streaming do L5X (módulos, tags alias, rastreamento de rotinas).
- `core/builder.py` — regra de atribuição de estação a cada tag/módulo.
- `core/excel_writer.py` — geração da planilha final.
- `gui/` — interface PyQt6.
- `theme.py`, `brand.py` — identidade visual Autolinx (mesma paleta/QSS do FaltGenerate e outras ferramentas).
- `app.ico` — ícone gerado por `gerar_icone.py` a partir de `brand.app_icon()`.

## Dados de cliente

Os arquivos `.L5X` de entrada e as planilhas geradas contêm dados de projetos de
clientes — não devem ser versionados neste repositório nem compartilhados fora do
ambiente de trabalho autorizado.
