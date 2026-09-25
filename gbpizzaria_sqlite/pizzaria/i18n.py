# -*- coding: utf-8 -*-
"""
i18n.py
Sistema de internacionalização simples.
As traduções ficam em locales/<lang>.json.
"""

import json
import os
from flask import session

SUPPORTED_LANGS = ['pt', 'en', 'es']
_LOCALES_DIR = os.path.join(os.path.dirname(__file__), 'locales')

# Carrega todos os arquivos de tradução uma vez ao iniciar
_translations: dict[str, dict] = {}
for _lang in SUPPORTED_LANGS:
    _path = os.path.join(_LOCALES_DIR, f'{_lang}.json')
    if os.path.exists(_path):
        with open(_path, 'r', encoding='utf-8') as _f:
            _translations[_lang] = json.load(_f)


def get_lang() -> str:
    """Retorna o idioma atual da sessão (padrão: 'pt')."""
    try:
        return session.get('lang', 'pt')
    except RuntimeError:
        return 'pt'


def t(key: str) -> str:
    """
    Retorna a tradução de `key` no idioma atual.
    Se a chave não existir, retorna a própria chave (fail-safe).
    """
    lang = get_lang()
    return (
        _translations.get(lang, {}).get(key)
        or _translations.get('pt', {}).get(key)
        or key
    )
