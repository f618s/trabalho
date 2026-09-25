# -*- coding: utf-8 -*-
"""
repositories.py — versão SQLAlchemy.
Mesma API pública do SQLite original.
"""

import json
from datetime import datetime
from sqlalchemy import func, desc, or_
from database import db
from models import (
    Usuario, Cliente, Produto, Pizza, Bebida, Pedido, ItemPedido,
    FechamentoCaixa, ResumoPagamento, ItemArquivado,
    Adicional, Combo, Fornecedor, Estoque, MovimentacaoEstoque,
    ItemPedidoDTO,
)


# ─────────────────────────────────────────────────────────── USUÁRIOS
class UsuarioRepositorio:
    def listar(self):
        return Usuario.query.order_by(Usuario.usuario).all()

    def buscar_por_login(self, usuario, senha):
        from werkzeug.security import generate_password_hash
        u = Usuario.query.get(usuario)
        if not u or not u.verificar_senha(senha):
            return None
        if not (u.senha.startswith("pbkdf2:") or u.senha.startswith("scrypt:")):
            u.senha = generate_password_hash(senha)
            db.session.commit()
        return u

    def buscar_por_nome(self, usuario):
        return Usuario.query.get(usuario)

    def existe(self, usuario):
        return Usuario.query.get(usuario) is not None

    def existe_cpf(self, cpf):
        return Usuario.query.filter_by(cpf=cpf).first() is not None

    def existe_email(self, email):
        return Usuario.query.filter_by(email=(email or '').lower()).first() is not None

    def contar_gerentes(self):
        return Usuario.query.filter_by(perfil='gerente').count()

    def adicionar(self, usuario_obj):
        from werkzeug.security import generate_password_hash
        senha = usuario_obj.senha
        if not (senha.startswith("pbkdf2:") or senha.startswith("scrypt:")):
            senha = generate_password_hash(senha)

        perfil = usuario_obj.perfil
        if Usuario.query.count() == 0:
            perfil = 'gerente'

        u = Usuario(
            usuario=usuario_obj.usuario,
            senha=senha,
            cpf=usuario_obj.cpf,
            email=(usuario_obj.email or '').lower(),
            perfil=perfil,
        )
        db.session.add(u)
        db.session.commit()
        return u

    def definir_perfil(self, usuario, perfil):
        if perfil not in ('funcionario', 'gerente'):
            return False
        u = Usuario.query.get(usuario)
        if not u:
            return False
        u.perfil = perfil
        db.session.commit()
        return True

    def remover(self, usuario):
        u = Usuario.query.get(usuario)
        if u:
            db.session.delete(u)
            db.session.commit()


# ─────────────────────────────────────────────────────────── CLIENTES
class ClienteRepositorio:
    def listar(self):
        return Cliente.query.order_by(Cliente.nome).all()

    def buscar(self, valor):
        return Cliente.query.filter(
            or_(
                Cliente.cpf == valor,
                Cliente.telefone == valor,
                func.lower(Cliente.nome) == (valor or '').lower(),
            )
        ).first()

    def existe_cpf(self, cpf):
        return Cliente.query.filter_by(cpf=cpf).first() is not None

    def existe_telefone(self, telefone):
        return Cliente.query.filter_by(telefone=telefone).first() is not None

    def adicionar(self, cliente_obj):
        c = Cliente(nome=cliente_obj.nome, cpf=cliente_obj.cpf,
                    telefone=cliente_obj.telefone)
        db.session.add(c)
        db.session.commit()
        return c


# ─────────────────────────────────────────────────────────── PRODUTOS
class ProdutoRepositorio:
    def listar(self):
        return Produto.query.order_by(Produto.tipo, Produto.nome).all()

    def listar_ativos(self):
        return (Produto.query
                .filter_by(ativo=True)
                .order_by(Produto.tipo, Produto.nome).all())

    def listar_pizzas(self, apenas_ativas=False):
        q = Pizza.query
        if apenas_ativas:
            q = q.filter_by(ativo=True)
        return q.order_by(Pizza.nome).all()

    def listar_bebidas(self, apenas_ativas=False):
        q = Bebida.query
        if apenas_ativas:
            q = q.filter_by(ativo=True)
        return q.order_by(Bebida.nome).all()

    def buscar_por_id(self, produto_id):
        return Produto.query.get(produto_id)

    def adicionar(self, produto_obj):
        if isinstance(produto_obj, Pizza):
            p = Pizza(nome=produto_obj.nome,
                      precos=produto_obj.precos_dict,
                      ativo=produto_obj.ativo)
        else:
            p = Bebida(nome=produto_obj.nome,
                       preco=produto_obj.preco,
                       ativo=produto_obj.ativo)
        db.session.add(p)
        db.session.flush()

        if not Estoque.query.get(p.id):
            db.session.add(Estoque(produto_id=p.id, quantidade=0,
                                   minimo=5, unidade='un'))
        db.session.commit()
        return p

    def alternar_status(self, produto_id):
        p = Produto.query.get(produto_id)
        if not p:
            return None
        p.ativo = not p.ativo
        db.session.commit()
        return p

    def dict_pizzas_para_template(self, apenas_ativas=True):
        return {p.nome: p.precos_dict for p in self.listar_pizzas(apenas_ativas)}

    def dict_bebidas_para_template(self, apenas_ativas=True):
        return {b.nome: b.preco for b in self.listar_bebidas(apenas_ativas)}


# ─────────────────────────────────────────────────────────── ADICIONAIS
class AdicionalRepositorio:
    def listar(self, apenas_ativos=False, aplica=None):
        q = Adicional.query
        if apenas_ativos:
            q = q.filter_by(ativo=True)
        if aplica in ('pizza', 'bebida'):
            q = q.filter(or_(Adicional.aplica == aplica,
                             Adicional.aplica == 'ambos'))
        return q.order_by(Adicional.nome).all()

    def buscar_por_id(self, adic_id):
        return Adicional.query.get(adic_id)

    def adicionar(self, adicional_obj):
        a = Adicional(nome=adicional_obj.nome, preco=adicional_obj.preco,
                      ativo=adicional_obj.ativo, aplica=adicional_obj.aplica)
        db.session.add(a)
        db.session.commit()
        return a

    def alternar_status(self, adic_id):
        a = Adicional.query.get(adic_id)
        if not a:
            return None
        a.ativo = not a.ativo
        db.session.commit()
        return a

    def remover(self, adic_id):
        a = Adicional.query.get(adic_id)
        if a:
            db.session.delete(a)
            db.session.commit()

    def dict_para_template(self, aplica=None):
        return {a.id: {"nome": a.nome, "preco": a.preco, "aplica": a.aplica}
                for a in self.listar(apenas_ativos=True, aplica=aplica)}


# ─────────────────────────────────────────────────────────── COMBOS
class ComboRepositorio:
    def listar(self, apenas_ativos=False):
        q = Combo.query
        if apenas_ativos:
            q = q.filter_by(ativo=True)
        return q.order_by(Combo.nome).all()

    def buscar_por_id(self, combo_id):
        return Combo.query.get(combo_id)

    def adicionar(self, combo_obj):
        c = Combo(nome=combo_obj.nome, descricao=combo_obj.descricao,
                  desconto=combo_obj.desconto, ativo=combo_obj.ativo,
                  itens_json=json.dumps(combo_obj.itens, ensure_ascii=False))
        db.session.add(c)
        db.session.commit()
        return c

    def alternar_status(self, combo_id):
        c = Combo.query.get(combo_id)
        if not c:
            return None
        c.ativo = not c.ativo
        db.session.commit()
        return c

    def remover(self, combo_id):
        c = Combo.query.get(combo_id)
        if c:
            db.session.delete(c)
            db.session.commit()


# ─────────────────────────────────────────────────────────── PEDIDOS
class PedidoRepositorio:
    def listar(self):
        return Pedido.query.order_by(Pedido.id).all()

    def buscar_por_id(self, pedido_id):
        return Pedido.query.get(pedido_id)

    def adicionar(self, pedido_obj, itens_dto=None):
        """
        Persiste o pedido + itens.
        - pedido_obj: instância de Pedido (ORM)
        - itens_dto: lista de ItemPedidoDTO (opcional)
        """
        p = Pedido(
            atendente=pedido_obj.atendente,
            cliente=pedido_obj.cliente,
            tipo_entrega=pedido_obj.tipo_entrega,
            endereco=pedido_obj.endereco,
            taxa_entrega=pedido_obj.taxa_entrega,
            forma_pagamento=pedido_obj.forma_pagamento,
            teve_desconto=pedido_obj.teve_desconto,
            data=pedido_obj.data,
            status=pedido_obj.status,
            observacoes=pedido_obj.observacoes,
            combo_id=pedido_obj.combo_id,
            combo_desconto=pedido_obj.combo_desconto,
            entrega_status=pedido_obj.entrega_status or 'preparando',
        )
        db.session.add(p)
        db.session.flush()

        # Aceita itens de várias origens
        itens = itens_dto or getattr(pedido_obj, '_itens_dto', None) or getattr(pedido_obj, 'itens', [])

        for item in itens:
            i = ItemPedido(
                pedido_id=p.id,
                tipo=item.tipo,
                nome=item.nome,
                preco=item.preco,
                quantidade=item.quantidade,
                adicionais_json=json.dumps(
                    getattr(item, 'adicionais', []) or [], ensure_ascii=False),
            )
            db.session.add(i)

        db.session.commit()

        # Recarrega para popular .itens
        db.session.refresh(p)
        return p

    def atualizar_status(self, pedido_id):
        p = Pedido.query.get(pedido_id)
        if not p:
            return None, False
        mudou = p.avancar_status()
        if mudou:
            db.session.commit()
        return p, mudou

    def atualizar_entrega(self, pedido_id, motoboy=""):
        p = Pedido.query.get(pedido_id)
        if not p:
            return None, False
        mudou = p.avancar_entrega(motoboy)
        if mudou:
            db.session.commit()
        return p, mudou

    def cancelar(self, pedido_id, motivo=""):
        p = Pedido.query.get(pedido_id)
        if not p:
            return None, False
        cancelou = p.cancelar(motivo)
        if cancelou:
            db.session.commit()
        return p, cancelou

    def historico_cliente(self, nome_cliente):
        return (Pedido.query
                .filter(func.lower(Pedido.cliente) == (nome_cliente or '').lower())
                .order_by(desc(Pedido.id)).all())

    def listar_por_periodo(self, data_inicio, data_fim):
        return (Pedido.query
                .filter(Pedido.data.between(data_inicio, data_fim))
                .order_by(Pedido.id).all())

    def limpar(self):
        ItemPedido.query.delete()
        Pedido.query.delete()
        db.session.commit()

    def proximo_id(self, _pedidos=None):
        m = db.session.query(func.max(Pedido.id)).scalar()
        return (m or 0) + 1


# ─────────────────────────────────────────────────────────── CAIXA
class CaixaRepositorio:
    def listar(self):
        return FechamentoCaixa.query.order_by(FechamentoCaixa.id).all()

    def adicionar(self, fechamento_obj, resumo_pagamentos=None, itens_arquivados=None):
        f = FechamentoCaixa(
            usuario=fechamento_obj.usuario,
            data_fechamento=fechamento_obj.data_fechamento,
            total_vendas=fechamento_obj.total_vendas,
            faturamento_total=fechamento_obj.faturamento_total,
        )
        db.session.add(f)
        db.session.flush()

        # Resumo por forma de pagamento
        resumo = resumo_pagamentos or getattr(fechamento_obj, 'resumo_pagamentos', {}) or {}
        for forma, valor in resumo.items():
            db.session.add(ResumoPagamento(
                fechamento_id=f.id, forma=forma, valor=valor))

        # Itens arquivados
        itens = itens_arquivados or getattr(fechamento_obj, 'itens_arquivados', []) or []
        for item in itens:
            db.session.add(ItemArquivado(
                fechamento_id=f.id, tipo=item['tipo'], nome=item['nome'],
                preco=item['preco'], quantidade=item['quantidade']))

        db.session.commit()
        fechamento_obj.id = f.id
        return f


# ─────────────────────────────────────────────────────────── ESTOQUE
class EstoqueRepositorio:
    def obter(self, produto_id):
        e = Estoque.query.get(produto_id)
        if not e:
            return None
        return {'quantidade': e.quantidade, 'minimo': e.minimo, 'unidade': e.unidade}

    def listar_com_produtos(self):
        rows = (db.session.query(Produto, Estoque)
                .outerjoin(Estoque, Estoque.produto_id == Produto.id)
                .order_by(Produto.tipo, Produto.nome).all())
        result = []
        for p, e in rows:
            qtd = e.quantidade if e else 0.0
            minimo = e.minimo if e else 5.0
            unidade = e.unidade if e else 'un'
            result.append({
                'id': p.id, 'tipo': p.tipo, 'nome': p.nome,
                'ativo': bool(p.ativo), 'quantidade': qtd,
                'minimo': minimo, 'unidade': unidade,
                'estoque_baixo': qtd <= minimo,
                'estoque_zerado': qtd <= 0,
            })
        return result

    def alertas(self):
        return [p for p in self.listar_com_produtos() if p['estoque_baixo']]

    def _garantir_estoque(self, produto_id):
        e = Estoque.query.get(produto_id)
        if not e:
            e = Estoque(produto_id=produto_id, quantidade=0, minimo=5, unidade='un')
            db.session.add(e)
            db.session.flush()
        return e

    def registrar_movimentacao(self, mov):
        db.session.add(mov)
        db.session.flush()

        e = self._garantir_estoque(mov.produto_id)
        if mov.tipo == 'entrada':
            e.quantidade = max(0, (e.quantidade or 0) + mov.quantidade)
        elif mov.tipo == 'saida':
            e.quantidade = max(0, (e.quantidade or 0) - mov.quantidade)
        elif mov.tipo == 'ajuste':
            e.quantidade = mov.quantidade

        db.session.commit()
        return mov

    def definir_minimo(self, produto_id, minimo, unidade='un'):
        e = self._garantir_estoque(produto_id)
        e.minimo = minimo
        e.unidade = unidade
        db.session.commit()

    def baixar_por_pedido(self, pedido, usuario=''):
        movs = []
        for item in pedido.itens:
            nome_base = item.nome.split(' (')[0].strip()
            partes = [p.strip() for p in nome_base.split('+')]
            for nome_parte in partes:
                prod = Produto.query.filter(
                    func.lower(Produto.nome) == nome_parte.lower()
                ).first()
                if not prod:
                    continue
                e = self._garantir_estoque(prod.id)
                e.quantidade = max(0, (e.quantidade or 0) - item.quantidade)
                mov = MovimentacaoEstoque(
                    produto_id=prod.id, tipo='saida',
                    quantidade=item.quantidade,
                    motivo=f"Venda — Pedido #{pedido.id}",
                    fornecedor='', preco_unitario=0.0, pedido_id=pedido.id,
                    usuario=usuario,
                    data=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                db.session.add(mov)
                movs.append({'produto_id': prod.id, 'quantidade': item.quantidade})
        db.session.commit()
        return movs

    def verificar_disponibilidade(self, itens):
        problemas = []
        for item in itens:
            nome_base = item.nome.split(' (')[0].strip()
            partes = [p.strip() for p in nome_base.split('+')]
            for nome_parte in partes:
                prod = Produto.query.filter(
                    func.lower(Produto.nome) == nome_parte.lower()
                ).first()
                if not prod:
                    continue
                e = Estoque.query.get(prod.id)
                qtd = e.quantidade if e else 0
                if qtd <= 0:
                    problemas.append({
                        'nome': prod.nome, 'disponivel': qtd,
                        'pedido': item.quantidade,
                    })
        return problemas

    def listar_movimentacoes(self, produto_id=None, tipo=None, limite=200):
        q = (db.session.query(MovimentacaoEstoque, Produto)
             .join(Produto, Produto.id == MovimentacaoEstoque.produto_id))
        if produto_id:
            q = q.filter(MovimentacaoEstoque.produto_id == produto_id)
        if tipo in ('entrada', 'saida', 'ajuste'):
            q = q.filter(MovimentacaoEstoque.tipo == tipo)
        rows = q.order_by(desc(MovimentacaoEstoque.id)).limit(limite).all()

        result = []
        for m, p in rows:
            d = m.to_dict()
            d['produto_nome'] = p.nome
            d['produto_tipo'] = p.tipo
            result.append(d)
        return result

    def resumo_compras(self, data_inicio=None, data_fim=None):
        q = db.session.query(
            func.coalesce(
                func.sum(MovimentacaoEstoque.quantidade * MovimentacaoEstoque.preco_unitario),
                0),
            func.count(MovimentacaoEstoque.id)
        ).filter(
            MovimentacaoEstoque.tipo == 'entrada',
            MovimentacaoEstoque.preco_unitario > 0,
        )
        if data_inicio:
            q = q.filter(func.date(MovimentacaoEstoque.data) >= data_inicio)
        if data_fim:
            q = q.filter(func.date(MovimentacaoEstoque.data) <= data_fim)
        total, n = q.one()
        return {'total': float(total or 0), 'n_compras': int(n or 0)}


# ─────────────────────────────────────────────────────────── FORNECEDORES
class FornecedorRepositorio:
    def listar(self, apenas_ativos=False):
        q = Fornecedor.query
        if apenas_ativos:
            q = q.filter_by(ativo=True)
        return q.order_by(Fornecedor.nome).all()

    def buscar_por_id(self, f_id):
        return Fornecedor.query.get(f_id)

    def adicionar(self, fornecedor_obj):
        f = Fornecedor(
            nome=fornecedor_obj.nome, cnpj=fornecedor_obj.cnpj,
            telefone=fornecedor_obj.telefone, email=fornecedor_obj.email,
            endereco=fornecedor_obj.endereco, obs=fornecedor_obj.obs,
            ativo=fornecedor_obj.ativo)
        db.session.add(f)
        db.session.commit()
        return f

    def atualizar(self, f_id, dados):
        f = Fornecedor.query.get(f_id)
        if not f:
            return None
        f.nome = dados['nome']
        f.cnpj = dados['cnpj']
        f.telefone = dados['telefone']
        f.email = dados['email']
        f.endereco = dados['endereco']
        f.obs = dados['obs']
        db.session.commit()
        return f

    def alternar_status(self, f_id):
        f = Fornecedor.query.get(f_id)
        if not f:
            return None
        f.ativo = not f.ativo
        db.session.commit()
        return f

    def remover(self, f_id):
        f = Fornecedor.query.get(f_id)
        if f:
            db.session.delete(f)
            db.session.commit()

    def historico_compras(self, fornecedor_id, limite=100):
        rows = (db.session.query(MovimentacaoEstoque, Produto)
                .join(Produto, Produto.id == MovimentacaoEstoque.produto_id)
                .filter(MovimentacaoEstoque.fornecedor_id == fornecedor_id)
                .order_by(desc(MovimentacaoEstoque.id))
                .limit(limite).all())
        result = []
        for m, p in rows:
            d = m.to_dict()
            d['produto_nome'] = p.nome
            d['produto_tipo'] = p.tipo
            result.append(d)
        return result