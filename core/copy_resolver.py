# -*- coding: utf-8 -*-
"""
Traduz o "AliasFor" de uma tag para o endereço físico real do módulo.

Ponto central: em Logix, endereço de módulo usa DOIS-PONTOS
("_005T02BM01:I1.Data[0].1"). Um caminho com PONTO ("_005T02BM01.DI01.1") é
uma tag de programa — mesmo quando ela tem exatamente o mesmo nome do módulo.
Essas tags são "espelhos" do módulo, preenchidas por uma instrução COP/CPS/MOV
dentro das rotinas de atualização de entrada/saída.

Exemplo (rotinas L000/L001 de atualização de entrada/saída):
    CPS(_005T02BM01:I1.Data[0], _005T02BM01.DI01, 4)
    CPS(_005T02BM01.Out,        _005T02BM01:O1.Data[0], 4)

    _005T02BM01.DI01.1  ->  _005T02BM01:I1.Data[0].1
    _005T02BM01.DI02.1  ->  _005T02BM01:I1.Data[1].1
    _005T02BM01.Out.5   ->  _005T02BM01:O1.Data[0].5

O deslocamento vem da POSIÇÃO do membro dentro do UDT (não do número no nome):
o tipo P_FESTO_VI_4832 tem DI01..DI05 e depois pula para DI11..DI15, então
contar pelo número do nome daria errado. O bit é preservado como está.

Duas formas de espelho são tratadas:
  A) índice por colchete   -> "_010TT01.I[0].0"      (deslocamento = índice)
  B) membro nomeado do UDT -> "_005T02BM01.DI02.1"   (deslocamento = posição do membro)

Pressupõe cópia espelhada, na mesma ordem dos dois lados (confirmado em campo).
"""
import re

INSTR_RE = re.compile(r'\b(COP|CPS|MOV)\(([^()]*)\)')
IDX_BIT_RE = re.compile(r'^(?P<base>.+)\[(?P<idx>\d+)\]\.(?P<bit>\d+)$')
IDX_ONLY_RE = re.compile(r'^(?P<base>.+)\[(?P<idx>\d+)\]$')
MEMBER_BIT_RE = re.compile(r'^(?P<tag>[A-Za-z_]\w*)\.(?P<member>[A-Za-z_]\w*)\.(?P<bit>\d+)$')
MEMBER_ONLY_RE = re.compile(r'^(?P<tag>[A-Za-z_]\w*)\.(?P<member>[A-Za-z_]\w*)$')
TRAILING_IDX_RE = re.compile(r'^(?P<base>.+)\[(?P<idx>\d+)\]$')


def is_module_address(operand):
    """Endereço de módulo em Logix sempre usa ':' (ex.: 'Mod:I1.Data[0]')."""
    return ":" in operand


def _split_trailing_index(operand):
    """'Tag.Membro[3]' -> ('Tag.Membro', 3); sem colchete -> (operando, 0)."""
    m = TRAILING_IDX_RE.match(operand)
    if m:
        return m.group("base"), int(m.group("idx"))
    return operand, 0


def _member_positions(datatype_members):
    """Lista de membros do UDT -> {nome do membro: posição em elementos}."""
    pos = {}
    n = 0
    for member in datatype_members:
        pos[member["Name"]] = n
        n += member.get("Dim", 1)
    return pos


def _parse_buffer_operand(operand, base_tags):
    """
    Interpreta o lado "espelho" de uma cópia. Devolve
    (base, membro, indice) onde só um entre membro/indice é usado:
      "_010TT01.I[0]"     -> ("_010TT01.I", None,   0)
      "_005T02BM01.DI01"  -> ("_005T02BM01", "DI01", 0)   [se a tag base é conhecida]
      "MinhaTag"          -> ("MinhaTag",   None,   0)
    """
    base, idx = _split_trailing_index(operand)
    if idx or "[" in operand:
        return base, None, idx

    if "." in base:
        tag, _, member = base.rpartition(".")
        if tag in base_tags:
            return tag, member, 0
    return base, None, 0


def build_copy_ranges(update_routines_text, tags, base_tags):
    """Monta as faixas de cópia espelho<->módulo a partir das rotinas de atualização."""
    ranges = []
    for routine_name, text in update_routines_text.items():
        for instr, args_text in INSTR_RE.findall(text):
            args = [a.strip() for a in args_text.split(",")]

            if instr in ("COP", "CPS"):
                if len(args) != 3 or not args[2].lstrip("-").isdigit():
                    continue
                src, dest, length = args[0], args[1], int(args[2])
            elif instr == "MOV":
                if len(args) != 2:
                    continue
                src, dest, length = args[0], args[1], 1
            else:
                continue

            if not src or not dest:
                continue

            # um operando pode ser o NOME de um alias; nesse caso vale o que ele aponta
            src = tags.get(src, {}).get("AliasFor") or src
            dest = tags.get(dest, {}).get("AliasFor") or dest

            src_is_mod = is_module_address(src)
            dest_is_mod = is_module_address(dest)
            if src_is_mod == dest_is_mod:
                # os dois (ou nenhum) são endereço de módulo -> sentido indefinido, pula
                continue

            if src_is_mod:
                module_base, module_start = _split_trailing_index(src)
                buf_base, buf_member, buf_idx = _parse_buffer_operand(dest, base_tags)
            else:
                module_base, module_start = _split_trailing_index(dest)
                buf_base, buf_member, buf_idx = _parse_buffer_operand(src, base_tags)

            ranges.append({
                "buffer_base": buf_base,
                "buffer_member": buf_member,
                "buffer_start": buf_idx,
                "module_base": module_base,
                "module_start": module_start,
                "length": length,
                "routine": routine_name,
            })
    return ranges


def resolve_physical(alias_for, copy_ranges, datatypes=None, base_tags=None):
    """Devolve o endereço de módulo por trás de um AliasFor de tag, ou None."""
    if not alias_for or is_module_address(alias_for):
        return None

    datatypes = datatypes or {}
    base_tags = base_tags or {}

    # forma A: indice por colchete, com ou sem bit ("_010TT01.I[0].0")
    bit = None
    m = IDX_BIT_RE.match(alias_for)
    if m:
        base, idx, bit = m.group("base"), int(m.group("idx")), m.group("bit")
    else:
        m = IDX_ONLY_RE.match(alias_for)
        if m:
            base, idx = m.group("base"), int(m.group("idx"))
        else:
            base = idx = None

    if base is not None:
        for r in copy_ranges:
            if r["buffer_member"] is not None or r["buffer_base"] != base:
                continue
            offset = idx - r["buffer_start"]
            if 0 <= offset < r["length"]:
                return _formatar(r["module_base"], r["module_start"] + offset, bit)
        return None

    # forma B: membro nomeado do UDT, com bit ("_005T02BM01.DI02.1")
    # ou a palavra inteira, sem bit ("PAW02BM01.DI01" - valor analogico)
    m = MEMBER_BIT_RE.match(alias_for)
    if m:
        tag, member, bit = m.group("tag"), m.group("member"), m.group("bit")
    else:
        m = MEMBER_ONLY_RE.match(alias_for)
        if not m:
            return None
        tag, member, bit = m.group("tag"), m.group("member"), None

    members = datatypes.get(base_tags.get(tag, ""), None)
    if not members:
        return None
    posicoes = _member_positions(members)
    if member not in posicoes:
        return None

    for r in copy_ranges:
        if r["buffer_member"] is None or r["buffer_base"] != tag:
            continue
        if r["buffer_member"] not in posicoes:
            continue
        offset = posicoes[member] - posicoes[r["buffer_member"]]
        if 0 <= offset < r["length"]:
            return _formatar(r["module_base"], r["module_start"] + offset, bit)
    return None


def _formatar(module_base, index, bit):
    endereco = f"{module_base}[{index}]"
    if bit is not None:
        endereco += f".{bit}"
    return endereco
