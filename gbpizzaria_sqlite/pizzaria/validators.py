# -*- coding: utf-8 -*-
"""
validators.py
Validações de CPF (algoritmo oficial da Receita Federal) e e-mail.
"""

import re


# ─────────────────────────────────────────────────── CPF
def _limpar_cpf(cpf: str) -> str:
    return re.sub(r'\D', '', cpf)


def validar_cpf(cpf: str) -> bool:
    """
    Valida CPF usando o algoritmo de dígitos verificadores da Receita Federal.
    Aceita com ou sem formatação (pontos e traço).
    """
    cpf = _limpar_cpf(cpf)

    if len(cpf) != 11:
        return False

    # Sequências inválidas (111.111.111-11, 000.000.000-00, etc.)
    if cpf == cpf[0] * 11:
        return False

    # Primeiro dígito verificador
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto
    if digito1 != int(cpf[9]):
        return False

    # Segundo dígito verificador
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto
    if digito2 != int(cpf[10]):
        return False

    return True


def formatar_cpf(cpf: str) -> str:
    """Formata CPF para exibição: 000.000.000-00"""
    cpf = _limpar_cpf(cpf)
    if len(cpf) == 11:
        return f'{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}'
    return cpf


# ─────────────────────────────────────────────────── E-MAIL
_EMAIL_RE = re.compile(
    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
)


def validar_email(email: str) -> bool:
    """
    Valida formato de e-mail via regex.
    Verifica: parte local válida @ domínio com TLD de ao menos 2 letras.
    """
    email = email.strip()
    if not email or len(email) > 254:
        return False
    if not _EMAIL_RE.match(email):
        return False
    # Parte local não pode ter '..' nem começar/terminar com '.'
    local = email.split('@')[0]
    if local.startswith('.') or local.endswith('.') or '..' in local:
        return False
    return True


# ─────────────────────────────────────────────────── TELEFONE
def _limpar_telefone(tel: str) -> str:
    return re.sub(r'\D', '', tel)


def validar_telefone(tel: str) -> bool:
    """
    Valida telefone brasileiro (fixo ou celular), com ou sem formatação.
    Aceita: (11) 91234-5678 / 11912345678 / (11) 3456-7890 / etc.
    Celular: 11 dígitos com DDD (2 dígitos) + 9 inicial.
    Fixo:    10 dígitos com DDD (2 dígitos).
    """
    digits = _limpar_telefone(tel)
    if len(digits) == 11:
        # celular: DDD (11-99) + 9 + 8 dígitos
        ddd = int(digits[:2])
        return 11 <= ddd <= 99 and digits[2] == '9'
    if len(digits) == 10:
        # fixo: DDD + número iniciando em 2-5
        ddd = int(digits[:2])
        return 11 <= ddd <= 99 and digits[2] in '2345'
    return False


def formatar_telefone(tel: str) -> str:
    """Formata telefone para exibição."""
    d = _limpar_telefone(tel)
    if len(d) == 11:
        return f'({d[:2]}) {d[2:7]}-{d[7:]}'
    if len(d) == 10:
        return f'({d[:2]}) {d[2:6]}-{d[6:]}'
    return tel


def validar_identificador_cliente(identificador: str):
    """
    Aceita CPF (000.000.000-00) ou telefone brasileiro com DDD.
    Para 11 dígitos, usa o formato visual para desambiguar:
      - se contém '.' => trata como CPF
      - caso contrário  => trata como celular
    Retorna ('cpf'|'telefone'|None, mensagem_de_erro|None).
    """
    digits = re.sub(r'\D', '', identificador)

    if len(digits) == 10:
        if validar_telefone(identificador):
            return 'telefone', None
        return None, 'Telefone fixo inválido. Use o formato (11) 3456-7890.'

    if len(digits) == 11:
        # Usa o formato visual para decidir: ponto decimal => CPF
        parece_cpf = '.' in identificador
        if parece_cpf:
            if validar_cpf(identificador):
                return 'cpf', None
            return None, 'CPF inválido. Verifique os dígitos verificadores.'
        else:
            if validar_telefone(identificador):
                return 'telefone', None
            # Pode ter digitado CPF sem formatação
            if validar_cpf(identificador):
                return 'cpf', None
            return None, 'Inválido. Para celular use (11) 91234-5678; para CPF use 000.000.000-00.'

    return None, 'Identificador inválido. Informe um CPF (000.000.000-00) ou telefone com DDD.'
# ─────────────────────────────────────────────────── CNPJ
def _limpar_cnpj(cnpj: str) -> str:
    return re.sub(r'\D', '', cnpj)


def validar_cnpj(cnpj: str) -> bool:
    """
    Valida CNPJ usando o algoritmo oficial de dígitos verificadores.
    Aceita com ou sem formatação (pontos, barra, traço).
    """
    cnpj = _limpar_cnpj(cnpj)

    if len(cnpj) != 14:
        return False

    # Sequências inválidas (00000000000000, 11111111111111, etc.)
    if cnpj == cnpj[0] * 14:
        return False

    # Primeiro dígito verificador
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto
    if digito1 != int(cnpj[12]):
        return False

    # Segundo dígito verificador
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto
    if digito2 != int(cnpj[13]):
        return False

    return True


def formatar_cnpj(cnpj: str) -> str:
    """Formata CNPJ para exibição: 00.000.000/0000-00"""
    cnpj = _limpar_cnpj(cnpj)
    if len(cnpj) == 14:
        return f'{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}'
    return cnpj
