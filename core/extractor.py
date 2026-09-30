# -*- coding: utf-8 -*-
"""
Extração em streaming de um arquivo L5X (exportação Studio 5000 / RSLogix5000):
  - modules: todos os <Module> configurados na árvore de I/O
  - tags: todas as <Tag TagType="Alias"> (Name, AliasFor, Description)
  - tag_routines: para cada tag, em quais rotinas (RLL) o nome dela aparece

Não usa um parser XML completo (DOM) de propósito: os arquivos de origem podem
passar de 70 MB, e um parse em streaming linha a linha é muito mais rápido e
leve em memória para esse caso de uso específico (só precisamos de alguns
atributos e do texto das rotinas, não da árvore completa).

Também guarda o texto bruto (RLL) das rotinas de atualização de entrada/saída
(nome contendo "ATUALIZA" ou "AGGIORNA" — os dois padrões observados no
projeto), mais as definições de UDT e as tags base, usados por
core.copy_resolver para achar o endereço físico real por trás de tags
intermediárias copiadas do/para um módulo.
"""
import re
import time

ATTR_RE = re.compile(r'(\w+)="([^"]*)"')
WORD_RE = re.compile(r'\w+')
UPDATE_ROUTINE_RE = re.compile(r'ATUALIZA|AGGIORNA', re.I)


def parse_attrs(tag_text):
    return dict(ATTR_RE.findall(tag_text))


def extract_l5x(path, progress_cb=None, log_cb=None):
    """
    Lê um L5X e retorna (modules, tags, tag_routines, update_routines_text, datatypes, base_tags).

    progress_cb(lines_done): chamado periodicamente com o número de linhas já lidas.
    log_cb(msg): chamado para mensagens de log livres.
    """
    t0 = time.time()
    modules = {}
    tags = {}          # name -> {"AliasFor": str, "Description": str}
    tag_routines = {}  # tag_name -> set(routine_name)
    update_routines_text = {}  # routine_name -> texto bruto (rotinas de atualizacao E/S)
    datatypes = {}     # nome do UDT -> lista ordenada de membros de armazenamento
    base_tags = {}     # nome da tag base -> nome do DataType

    mode = None  # None, 'module', 'tag', 'routine', 'datatype'
    buf = []
    cur_ip = None
    cur_routine_name = None
    cur_update_buf = None
    cur_dt_name = None
    cur_dt_members = None
    lines_done = 0

    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            lines_done += 1
            if progress_cb and lines_done % 1_000_000 == 0:
                progress_cb(lines_done)

            if mode is None:
                if "<Module " in line:
                    mode = "module"
                    buf = [line]
                    cur_ip = None
                    if line.rstrip().endswith("/>"):
                        attrs = parse_attrs(line)
                        modules[attrs.get("Name")] = {
                            "CatalogNumber": attrs.get("CatalogNumber", ""),
                            "Vendor": attrs.get("Vendor", ""),
                            "ParentModule": attrs.get("ParentModule", ""),
                            "IP": None,
                        }
                        mode = None
                    continue
                elif '<Tag Name=' in line and 'TagType="Alias"' in line:
                    mode = "tag"
                    buf = [line]
                    if line.rstrip().endswith("/>"):
                        attrs = parse_attrs(line)
                        tags[attrs.get("Name")] = {
                            "AliasFor": attrs.get("AliasFor", ""),
                            "Description": "",
                        }
                        mode = None
                    continue
                elif '<Tag Name=' in line and 'TagType="Base"' in line:
                    attrs = parse_attrs(line)
                    if attrs.get("Name") and attrs.get("DataType"):
                        base_tags[attrs["Name"]] = attrs["DataType"]
                    continue
                elif "<DataType " in line:
                    attrs = parse_attrs(line)
                    cur_dt_name = attrs.get("Name")
                    cur_dt_members = []
                    if line.rstrip().endswith("/>"):
                        cur_dt_name = None
                        cur_dt_members = None
                        continue
                    mode = "datatype"
                    continue
                elif "<Routine Name=" in line:
                    attrs = parse_attrs(line)
                    cur_routine_name = attrs.get("Name")
                    cur_update_buf = [] if (cur_routine_name and UPDATE_ROUTINE_RE.search(cur_routine_name)) else None
                    if line.rstrip().endswith("/>"):
                        cur_routine_name = None
                        cur_update_buf = None
                        continue
                    mode = "routine"
                    continue
                else:
                    continue

            elif mode == "module":
                buf.append(line)
                if "<Port " in line and cur_ip is None:
                    pattrs = parse_attrs(line)
                    if pattrs.get("Type") == "Ethernet":
                        cur_ip = pattrs.get("Address")
                if "</Module>" in line:
                    full_open = "".join(buf)
                    open_part = full_open.split(">", 1)[0]
                    attrs = parse_attrs(open_part)
                    modules[attrs.get("Name")] = {
                        "CatalogNumber": attrs.get("CatalogNumber", ""),
                        "Vendor": attrs.get("Vendor", ""),
                        "ParentModule": attrs.get("ParentModule", ""),
                        "IP": cur_ip,
                    }
                    mode = None
                    buf = []

            elif mode == "tag":
                buf.append(line)
                if "</Tag>" in line:
                    full = "".join(buf)
                    open_part = full.split(">", 1)[0]
                    attrs = parse_attrs(open_part)
                    desc = ""
                    m = re.search(r"<!\[CDATA\[(.*?)\]\]>", full, re.S)
                    if m:
                        desc = m.group(1).strip()
                    tags[attrs.get("Name")] = {
                        "AliasFor": attrs.get("AliasFor", ""),
                        "Description": desc,
                    }
                    mode = None
                    buf = []

            elif mode == "datatype":
                if "</DataType>" in line:
                    if cur_dt_name:
                        datatypes[cur_dt_name] = cur_dt_members
                    mode = None
                    cur_dt_name = None
                    cur_dt_members = None
                    continue
                if "<Member " in line:
                    attrs = parse_attrs(line)
                    # membros BIT sao apelidos de bit dentro de outro membro: nao ocupam
                    # posicao propria de armazenamento, entao ficam de fora da ordem.
                    if attrs.get("DataType") != "BIT" and attrs.get("Name"):
                        try:
                            dim = int(attrs.get("Dimension", "0"))
                        except ValueError:
                            dim = 0
                        cur_dt_members.append({"Name": attrs["Name"], "Dim": max(1, dim)})

            elif mode == "routine":
                if "</Routine>" in line:
                    if cur_update_buf is not None:
                        update_routines_text[cur_routine_name] = "".join(cur_update_buf)
                    mode = None
                    cur_routine_name = None
                    cur_update_buf = None
                    continue
                if cur_update_buf is not None:
                    cur_update_buf.append(line)
                if cur_routine_name:
                    for tok in WORD_RE.findall(line):
                        s = tag_routines.get(tok)
                        if s is None:
                            tag_routines[tok] = {cur_routine_name}
                        else:
                            s.add(cur_routine_name)

    # mantem no tag_routines somente entradas que correspondem a tags reais
    # (reduz ruido e tamanho do resultado)
    tag_names = set(tags.keys())
    tag_routines_filtered = {k: sorted(v) for k, v in tag_routines.items() if k in tag_names}

    elapsed = time.time() - t0
    if log_cb:
        log_cb(f"  {len(modules)} modulos, {len(tags)} tags alias, "
                f"{len(tag_routines_filtered)} tags rastreadas em rotinas, "
                f"{len(update_routines_text)} rotina(s) de atualizacao E/S ({elapsed:.1f}s)")

    return modules, tags, tag_routines_filtered, update_routines_text, datatypes, base_tags
