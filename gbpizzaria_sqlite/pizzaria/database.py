# -*- coding: utf-8 -*-
"""
database.py
Configuração do Flask-SQLAlchemy.
"""

import os
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.environ.get('DB_PATH',
                         os.path.join(os.path.dirname(__file__), 'pizzaria.db'))

db = SQLAlchemy()


def build_uri(path: str = None) -> str:
    path = path or DB_PATH
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(__file__), path)
    return f"sqlite:///{path}"


def init_app(app):
    app.config['SQLALCHEMY_DATABASE_URI'] = build_uri()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {'check_same_thread': False},
    }
    db.init_app(app)

    with app.app_context():
        from models import (  # noqa: F401
            Usuario, Cliente, Produto, Pizza, Bebida, Pedido, ItemPedido,
            FechamentoCaixa, ResumoPagamento, ItemArquivado,
            Adicional, Combo, Fornecedor, Estoque, MovimentacaoEstoque,
            ItemPedidoDTO,
        )
        db.create_all()