# -*- coding: utf-8 -*-
"""
models.py
Modelos SQLAlchemy + DTOs de domínio.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from database import db


# ═══════════════════════════════════════════════════════════════
# DTO (não persiste no banco — usado em memória durante o request)
# ═══════════════════════════════════════════════════════════════

@dataclass
class ItemPedidoDTO:
    tipo: str
    nome: str
    preco: float
    quantidade: int = 1
    adicionais: list = field(default_factory=list)

    @property
    def total_adicionais(self):
        return sum(float(a.get('preco', 0)) for a in self.adicionais) * self.quantidade

    @property
    def total(self):
        base = self.preco + sum(float(a.get('preco', 0)) for a in self.adicionais)
        return base * self.quantidade

    def to_dict(self):
        return {"tipo": self.tipo, "nome": self.nome,
                "preco": self.preco, "quantidade": self.quantidade,
                "adicionais": self.adicionais}

    @staticmethod
    def from_dict(d):
        return ItemPedidoDTO(
            tipo=d.get("tipo", ""), nome=d.get("nome", ""),
            preco=float(d.get("preco", 0.0)), quantidade=int(d.get("quantidade", 1)),
            adicionais=d.get("adicionais", []))


# ═══════════════════════════════════════════════════════════════
# MODELOS SQLALCHEMY
# ═══════════════════════════════════════════════════════════════

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    PERFIL_FUNCIONARIO = 'funcionario'
    PERFIL_GERENTE     = 'gerente'

    usuario = db.Column(db.String, primary_key=True)
    senha   = db.Column(db.String, nullable=False)
    cpf     = db.Column(db.String, default='')
    email   = db.Column(db.String, default='')
    perfil  = db.Column(db.String, default='funcionario')

    @property
    def is_gerente(self):
        return self.perfil == self.PERFIL_GERENTE

    def verificar_senha(self, senha):
        from werkzeug.security import check_password_hash
        if self.senha.startswith('pbkdf2:') or self.senha.startswith('scrypt:'):
            return check_password_hash(self.senha, senha)
        return self.senha == senha

    def to_dict(self):
        return {"usuario": self.usuario, "senha": self.senha,
                "cpf": self.cpf, "email": self.email, "perfil": self.perfil}

    @staticmethod
    def from_dict(d):
        return Usuario(usuario=d["usuario"], senha=d["senha"],
                       cpf=d.get("cpf", ""), email=d.get("email", ""),
                       perfil=d.get("perfil", "funcionario"))


class Cliente(db.Model):
    __tablename__ = 'clientes'
    id       = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome     = db.Column(db.String, nullable=False)
    cpf      = db.Column(db.String, default='')
    telefone = db.Column(db.String, default='')

    def to_dict(self):
        return {"nome": self.nome, "cpf": self.cpf, "telefone": self.telefone}

    @staticmethod
    def from_dict(d):
        return Cliente(nome=d["nome"], cpf=d.get("cpf", ""), telefone=d.get("telefone", ""))


class Produto(db.Model):
    __tablename__ = 'produtos'
    PERCENTUAL_DESCONTO_CLIENTE = 0.10

    id     = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tipo   = db.Column(db.String, nullable=False)
    nome   = db.Column(db.String, nullable=False)
    ativo  = db.Column(db.Boolean, default=True)
    precos = db.Column(db.Text, default='{}')
    preco  = db.Column(db.Float, default=0.0)

    __mapper_args__ = {
        'polymorphic_on': tipo,
        'polymorphic_identity': 'Produto',
    }

    def preco_base(self):
        return self.preco or 0.0

    @staticmethod
    def from_dict(d):
        if d.get("tipo") == "Pizza":
            return Pizza.from_dict(d)
        return Bebida.from_dict(d)


class Pizza(Produto):
    TAMANHOS = ["Broto", "Média", "Grande", "Gigante"]
    __mapper_args__ = {'polymorphic_identity': 'Pizza'}

    def __init__(self, id=None, nome='', precos=None, ativo=True, **kw):
        # Aceita tanto dict quanto string JSON
        if isinstance(precos, str):
            precos_str = precos
        else:
            precos_str = json.dumps(precos or {}, ensure_ascii=False)
        super().__init__(id=id, nome=nome, ativo=ativo, tipo='Pizza',
                         precos=precos_str)
        for k, v in kw.items():
            setattr(self, k, v)

    @property
    def precos_dict(self):
        try:
            raw = json.loads(self.precos) if self.precos else {}
        except Exception:
            raw = {}
        return {t: float(raw.get(t, 0.0)) for t in self.TAMANHOS}

    def preco_por_tamanho(self, tamanho):
        return self.precos_dict.get(tamanho, 0.0)

    def preco_base(self):
        valores = [v for v in self.precos_dict.values() if v > 0]
        return min(valores) if valores else 0.0

    def to_dict(self):
        return {"id": self.id, "tipo": "Pizza", "nome": self.nome,
                "ativo": self.ativo, "precos": self.precos_dict}

    @staticmethod
    def from_dict(d):
        return Pizza(id=d.get("id"), nome=d["nome"],
                     precos=d.get("precos", {}), ativo=d.get("ativo", True))


class Bebida(Produto):
    __mapper_args__ = {'polymorphic_identity': 'Bebida'}

    def __init__(self, id=None, nome='', preco=0.0, ativo=True, **kw):
        super().__init__(id=id, nome=nome, ativo=ativo, tipo='Bebida',
                         preco=float(preco or 0))
        for k, v in kw.items():
            setattr(self, k, v)

    def preco_base(self):
        return self.preco or 0.0

    def to_dict(self):
        return {"id": self.id, "tipo": "Bebida", "nome": self.nome,
                "ativo": self.ativo, "preco": self.preco}

    @staticmethod
    def from_dict(d):
        return Bebida(id=d.get("id"), nome=d["nome"],
                      preco=d.get("preco", 0.0), ativo=d.get("ativo", True))


class Pedido(db.Model):
    __tablename__ = 'pedidos'
    STATUS_PENDENTE    = "Pendente"
    STATUS_NO_FORNO    = "No forno"
    STATUS_PRONTO      = "Pronto"
    STATUS_CANCELADO   = "Cancelado"

    ENTREGA_PREPARANDO = "preparando"
    ENTREGA_SAIU       = "saiu"
    ENTREGA_ENTREGUE   = "entregue"

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    atendente      = db.Column(db.String, nullable=False)
    cliente        = db.Column(db.String, default='')
    tipo_entrega   = db.Column(db.String, nullable=False)
    endereco       = db.Column(db.String, default='')
    taxa_entrega   = db.Column(db.Float, default=0.0)
    forma_pagamento = db.Column(db.String, nullable=False)
    teve_desconto  = db.Column(db.Boolean, default=False)
    data           = db.Column(db.String, nullable=False)
    status         = db.Column(db.String, default='Pendente')
    observacoes    = db.Column(db.String, default='')
    motivo_cancelamento = db.Column(db.String, default='')
    combo_id       = db.Column(db.Integer, nullable=True)
    combo_desconto = db.Column(db.Float, default=0.0)
    entrega_status = db.Column(db.String, default='preparando')
    entrega_motoboy = db.Column(db.String, default='')
    entrega_saiu_em = db.Column(db.String, default='')
    entrega_entregue_em = db.Column(db.String, default='')

    itens = db.relationship('ItemPedido', backref='pedido',
                            cascade='all, delete-orphan', lazy='joined')

    @property
    def subtotal_itens(self):
        return sum(i.total for i in self.itens)

    @property
    def preco_original(self):
        return self.subtotal_itens + (self.taxa_entrega or 0.0)

    @property
    def preco_final(self):
        subtotal = self.subtotal_itens
        if self.teve_desconto:
            subtotal *= (1 - Produto.PERCENTUAL_DESCONTO_CLIENTE)
        return max(subtotal - (self.combo_desconto or 0.0), 0.0) + (self.taxa_entrega or 0.0)

    def avancar_status(self):
        if self.status == self.STATUS_CANCELADO: return False
        if self.status == self.STATUS_PENDENTE:
            self.status = self.STATUS_NO_FORNO; return True
        if self.status == self.STATUS_NO_FORNO:
            self.status = self.STATUS_PRONTO; return True
        return False

    def cancelar(self, motivo=""):
        if self.status == self.STATUS_PRONTO: return False
        self.status = self.STATUS_CANCELADO
        self.motivo_cancelamento = motivo
        return True

    def avancar_entrega(self, motoboy=""):
        if self.tipo_entrega != 'Entrega': return False
        if self.entrega_status == self.ENTREGA_PREPARANDO:
            self.entrega_status = self.ENTREGA_SAIU
            self.entrega_saiu_em = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if motoboy: self.entrega_motoboy = motoboy
            return True
        if self.entrega_status == self.ENTREGA_SAIU:
            self.entrega_status = self.ENTREGA_ENTREGUE
            self.entrega_entregue_em = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            return True
        return False

    def to_dict(self):
        return {
            "id": self.id, "atendente": self.atendente, "cliente": self.cliente,
            "itens": [i.to_dict() for i in self.itens], "tipo_entrega": self.tipo_entrega,
            "endereco": self.endereco, "taxa_entrega": self.taxa_entrega,
            "forma_pagamento": self.forma_pagamento, "preco_original": self.preco_original,
            "preco_final": self.preco_final, "teve_desconto": self.teve_desconto,
            "data": self.data, "status": self.status,
            "observacoes": self.observacoes,
            "motivo_cancelamento": self.motivo_cancelamento,
            "combo_id": self.combo_id, "combo_desconto": self.combo_desconto,
            "entrega_status": self.entrega_status,
            "entrega_motoboy": self.entrega_motoboy,
            "entrega_saiu_em": self.entrega_saiu_em,
            "entrega_entregue_em": self.entrega_entregue_em,
        }


class ItemPedido(db.Model):
    __tablename__ = 'itens_pedido'
    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pedido_id   = db.Column(db.Integer, db.ForeignKey('pedidos.id', ondelete='CASCADE'))
    tipo        = db.Column(db.String, nullable=False)
    nome        = db.Column(db.String, nullable=False)
    preco       = db.Column(db.Float, nullable=False)
    quantidade  = db.Column(db.Integer, default=1)
    adicionais_json = db.Column(db.Text, default='[]')

    @property
    def adicionais(self):
        try:
            return json.loads(self.adicionais_json) if self.adicionais_json else []
        except Exception:
            return []

    @property
    def total_adicionais(self):
        return sum(float(a.get('preco', 0)) for a in self.adicionais) * self.quantidade

    @property
    def total(self):
        base = self.preco + sum(float(a.get('preco', 0)) for a in self.adicionais)
        return base * self.quantidade

    def to_dict(self):
        return {"tipo": self.tipo, "nome": self.nome,
                "preco": self.preco, "quantidade": self.quantidade,
                "adicionais": self.adicionais}


class FechamentoCaixa(db.Model):
    __tablename__ = 'fechamentos_caixa'
    FORMAS_PAGAMENTO_PADRAO = ["Dinheiro","Cartão de Crédito","Cartão de Débito","PIX"]

    id                = db.Column(db.Integer, primary_key=True, autoincrement=True)
    usuario           = db.Column(db.String, nullable=False)
    data_fechamento   = db.Column(db.String, nullable=False)
    total_vendas      = db.Column(db.Integer, default=0)
    faturamento_total = db.Column(db.Float, default=0.0)

    resumo = db.relationship('ResumoPagamento', backref='fechamento',
                             cascade='all, delete-orphan', lazy='joined')
    itens  = db.relationship('ItemArquivado', backref='fechamento',
                             cascade='all, delete-orphan', lazy='joined')

    @property
    def resumo_pagamentos(self):
        return {r.forma: r.valor for r in self.resumo}

    @property
    def itens_arquivados(self):
        return [{'tipo': i.tipo, 'nome': i.nome, 'preco': i.preco,
                 'quantidade': i.quantidade} for i in self.itens]

    def to_dict(self):
        return {"id": self.id, "data_fechamento": self.data_fechamento,
                "usuario": self.usuario, "total_vendas": self.total_vendas,
                "faturamento_total": self.faturamento_total,
                "resumo_pagamentos": self.resumo_pagamentos,
                "itens_arquivados": self.itens_arquivados}


class ResumoPagamento(db.Model):
    __tablename__ = 'resumo_pagamentos'
    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fechamento_id = db.Column(db.Integer, db.ForeignKey('fechamentos_caixa.id', ondelete='CASCADE'))
    forma         = db.Column(db.String, nullable=False)
    valor         = db.Column(db.Float, default=0.0)


class ItemArquivado(db.Model):
    __tablename__ = 'itens_arquivados'
    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fechamento_id = db.Column(db.Integer, db.ForeignKey('fechamentos_caixa.id', ondelete='CASCADE'))
    tipo          = db.Column(db.String, nullable=False)
    nome          = db.Column(db.String, nullable=False)
    preco         = db.Column(db.Float, nullable=False)
    quantidade    = db.Column(db.Integer, default=1)


class Adicional(db.Model):
    __tablename__ = 'adicionais'
    id     = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome   = db.Column(db.String, nullable=False)
    preco  = db.Column(db.Float, default=0.0)
    ativo  = db.Column(db.Boolean, default=True)
    aplica = db.Column(db.String, default='ambos')

    def to_dict(self):
        return {"id": self.id, "nome": self.nome, "preco": self.preco,
                "ativo": self.ativo, "aplica": self.aplica}

    @staticmethod
    def from_dict(d):
        return Adicional(id=d.get("id"), nome=d["nome"],
                         preco=d.get("preco", 0.0),
                         ativo=d.get("ativo", True),
                         aplica=d.get("aplica", "ambos"))


class Combo(db.Model):
    __tablename__ = 'combos'
    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome       = db.Column(db.String, nullable=False)
    descricao  = db.Column(db.String, default='')
    desconto   = db.Column(db.Float, default=0.0)
    ativo      = db.Column(db.Boolean, default=True)
    itens_json = db.Column(db.Text, default='[]')

    @property
    def itens(self):
        try:
            return json.loads(self.itens_json) if self.itens_json else []
        except Exception:
            return []

    @property
    def subtotal(self):
        return sum(float(i.get('preco', 0)) * int(i.get('quantidade', 1))
                   for i in self.itens)

    @property
    def preco_final(self):
        return max(self.subtotal - self.desconto, 0.0)

    def to_dict(self):
        return {"id": self.id, "nome": self.nome, "descricao": self.descricao,
                "desconto": self.desconto, "itens": self.itens,
                "ativo": self.ativo}

    @staticmethod
    def from_dict(d):
        return Combo(id=d.get("id"), nome=d["nome"],
                     descricao=d.get("descricao", ""),
                     desconto=d.get("desconto", 0.0),
                     ativo=d.get("ativo", True),
                     itens_json=json.dumps(d.get("itens", []), ensure_ascii=False))


class Fornecedor(db.Model):
    __tablename__ = 'fornecedores'
    id       = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome     = db.Column(db.String, nullable=False)
    cnpj     = db.Column(db.String, default='')
    telefone = db.Column(db.String, default='')
    email    = db.Column(db.String, default='')
    endereco = db.Column(db.String, default='')
    obs      = db.Column(db.String, default='')
    ativo    = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {"id": self.id, "nome": self.nome, "cnpj": self.cnpj,
                "telefone": self.telefone, "email": self.email,
                "endereco": self.endereco, "obs": self.obs, "ativo": self.ativo}

    @staticmethod
    def from_dict(d):
        return Fornecedor(id=d.get("id"), nome=d["nome"],
                          cnpj=d.get("cnpj", ""),
                          telefone=d.get("telefone", ""),
                          email=d.get("email", ""),
                          endereco=d.get("endereco", ""),
                          obs=d.get("obs", ""),
                          ativo=d.get("ativo", True))


class Estoque(db.Model):
    __tablename__ = 'estoque'
    produto_id = db.Column(db.Integer,
                           db.ForeignKey('produtos.id', ondelete='CASCADE'),
                           primary_key=True)
    quantidade = db.Column(db.Float, default=0.0)
    minimo     = db.Column(db.Float, default=5.0)
    unidade    = db.Column(db.String, default='un')


class MovimentacaoEstoque(db.Model):
    __tablename__ = 'movimentacoes_estoque'
    TIPO_ENTRADA = 'entrada'
    TIPO_SAIDA   = 'saida'
    TIPO_AJUSTE  = 'ajuste'

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    produto_id     = db.Column(db.Integer,
                               db.ForeignKey('produtos.id', ondelete='CASCADE'))
    tipo           = db.Column(db.String, nullable=False)
    quantidade     = db.Column(db.Float, nullable=False)
    motivo         = db.Column(db.String, default='')
    fornecedor     = db.Column(db.String, default='')
    fornecedor_id  = db.Column(db.Integer, nullable=True)
    preco_unitario = db.Column(db.Float, default=0.0)
    pedido_id      = db.Column(db.Integer, nullable=True)
    usuario        = db.Column(db.String, default='')
    data           = db.Column(db.String, nullable=False)

    def __init__(self, **kw):
        # Aceita tanto `MovimentacaoEstoque(produto_id=.., tipo=.., ...)`
        # quanto `MovimentacaoEstoque(id, produto_id, tipo, quantidade, ...)`
        # vindo de código legado.
        if 'id' in kw and isinstance(kw.get('id'), int):
            # posicional: id, produto_id, tipo, quantidade, motivo, fornecedor,
            # preco_unitario, pedido_id, usuario, data, fornecedor_id
            pass
        # Remove campos internos que o SQLAlchemy gerencia
        kw.pop('_sa_instance_state', None)
        super().__init__(**kw)

    @property
    def valor_total(self):
        return (self.quantidade or 0) * (self.preco_unitario or 0)

    def to_dict(self):
        return {"id": self.id, "produto_id": self.produto_id, "tipo": self.tipo,
                "quantidade": self.quantidade, "motivo": self.motivo,
                "fornecedor": self.fornecedor, "fornecedor_id": self.fornecedor_id,
                "preco_unitario": self.preco_unitario,
                "valor_total": self.valor_total,
                "pedido_id": self.pedido_id, "usuario": self.usuario,
                "data": self.data}