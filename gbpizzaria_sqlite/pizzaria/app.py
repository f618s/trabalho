# -*- coding: utf-8 -*-
"""
app.py
Aplicação Flask do GB.Pizzaria — Flask-SQLAlchemy.
"""

import json
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from datetime import datetime, timedelta
from collections import Counter
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

load_dotenv()

# ── Banco de dados (Flask-SQLAlchemy) ────────────────────────
from database import db, init_app as db_init_app

# ── Validações ───────────────────────────────────────────────
from validators import (
    validar_cpf, validar_email, validar_telefone,
    formatar_cpf, formatar_telefone,
    validar_cnpj, formatar_cnpj,
)

# ── Modelos SQLAlchemy ───────────────────────────────────────
from models import (
    Usuario, Cliente, Pizza, Bebida, ItemPedido, ItemPedidoDTO,
    Pedido, FechamentoCaixa, Adicional, Combo,
    MovimentacaoEstoque, Fornecedor,
)

# ── Repositórios ─────────────────────────────────────────────
from repositories import (
    UsuarioRepositorio, ClienteRepositorio, ProdutoRepositorio,
    PedidoRepositorio, CaixaRepositorio, AdicionalRepositorio,
    ComboRepositorio, EstoqueRepositorio, FornecedorRepositorio,
)

from pdf_generator import ComprovantePDF, RelatorioCaixaPDF
from i18n import t, get_lang, SUPPORTED_LANGS

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chave_padrao_insegura_troque_no_env")

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# ── Inicializa Flask-SQLAlchemy + cria tabelas ───────────────
db_init_app(app)


@app.after_request
def add_no_cache_headers(response):
    if app.debug:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)


@app.errorhandler(429)
def rate_limit_handler(e):
    flash(t('login_erro_tentativas'), 'danger')
    return redirect(url_for('login'))


app.jinja_env.globals['t']        = t
app.jinja_env.globals['get_lang'] = get_lang
app.jinja_env.globals['SUPPORTED_LANGS'] = SUPPORTED_LANGS

# Repositórios
usuarios_repo     = UsuarioRepositorio()
clientes_repo     = ClienteRepositorio()
produtos_repo     = ProdutoRepositorio()
pedidos_repo      = PedidoRepositorio()
caixa_repo        = CaixaRepositorio()
adicionais_repo   = AdicionalRepositorio()
combos_repo       = ComboRepositorio()
estoque_repo      = EstoqueRepositorio()
fornecedores_repo = FornecedorRepositorio()


# ── Helpers de perfil ────────────────────────────────────────
def login_obrigatorio():
    return 'usuario' not in session


def _usuario_atual():
    if 'usuario' not in session:
        return None
    return usuarios_repo.buscar_por_nome(session['usuario'])


def _is_gerente():
    u = _usuario_atual()
    return bool(u and u.is_gerente)


def gerente_obrigatorio():
    if login_obrigatorio():
        return True
    if not _is_gerente():
        flash('Acesso restrito ao gerente.', 'danger')
        return True
    return False


app.jinja_env.globals['is_gerente'] = _is_gerente
app.jinja_env.globals['usuario_atual_obj'] = _usuario_atual


# ── Seed do cardápio ─────────────────────────────────────────
def _seed_cardapio():
    if not produtos_repo.listar():
        pizzas_iniciais = [
            Pizza(nome="Calabresa",           precos={"Broto": 25.0, "Média": 35.0, "Grande": 45.0, "Gigante": 55.0}),
            Pizza(nome="Frango com Catupiry", precos={"Broto": 28.0, "Média": 38.0, "Grande": 48.0, "Gigante": 58.0}),
            Pizza(nome="Marguerita",          precos={"Broto": 24.0, "Média": 34.0, "Grande": 44.0, "Gigante": 54.0}),
            Pizza(nome="Quatro Queijos",      precos={"Broto": 30.0, "Média": 40.0, "Grande": 50.0, "Gigante": 60.0}),
            Pizza(nome="Portuguesa",          precos={"Broto": 28.0, "Média": 38.0, "Grande": 48.0, "Gigante": 58.0}),
        ]
        bebidas_iniciais = [
            Bebida(nome="Coca-Cola Lata 350ml",   preco=6.0),
            Bebida(nome="Coca-Cola 2 Litros",    preco=12.0),
            Bebida(nome="Guaraná Antarctica 2L", preco=10.0),
            Bebida(nome="Água Mineral sem Gás",  preco=4.0),
            Bebida(nome="Suco de Laranja Prats", preco=9.0),
        ]
        for p in pizzas_iniciais + bebidas_iniciais:
            produtos_repo.adicionar(p)

    if not adicionais_repo.listar():
        iniciais = [
            Adicional(nome="Borda Catupiry",      preco=5.0, ativo=True, aplica='pizza'),
            Adicional(nome="Borda Cheddar",       preco=5.0, ativo=True, aplica='pizza'),
            Adicional(nome="Bacon extra",         preco=3.0, ativo=True, aplica='pizza'),
            Adicional(nome="Queijo extra",        preco=4.0, ativo=True, aplica='pizza'),
            Adicional(nome="Azeitona",            preco=2.0, ativo=True, aplica='pizza'),
            Adicional(nome="Cebola caramelizada", preco=3.0, ativo=True, aplica='pizza'),
        ]
        for a in iniciais:
            adicionais_repo.adicionar(a)

    if not combos_repo.listar():
        combos_iniciais = [
            Combo(nome="Combo Casal",
                  descricao="2 pizzas grandes + 1 refrigerante 2L",
                  desconto=10.0, ativo=True,
                  itens_json=json.dumps([
                      {"tipo":"Pizza","nome":"Pizza Grande 1","preco":45.0,"quantidade":1},
                      {"tipo":"Pizza","nome":"Pizza Grande 2","preco":45.0,"quantidade":1},
                      {"tipo":"Bebida","nome":"Refrigerante 2L","preco":12.0,"quantidade":1},
                  ], ensure_ascii=False)),
            Combo(nome="Combo Família",
                  descricao="3 pizzas grandes + 2 refrigerantes 2L",
                  desconto=20.0, ativo=True,
                  itens_json=json.dumps([
                      {"tipo":"Pizza","nome":"Pizza Grande 1","preco":45.0,"quantidade":1},
                      {"tipo":"Pizza","nome":"Pizza Grande 2","preco":45.0,"quantidade":1},
                      {"tipo":"Pizza","nome":"Pizza Grande 3","preco":45.0,"quantidade":1},
                      {"tipo":"Bebida","nome":"Refrigerante 2L","preco":12.0,"quantidade":2},
                  ], ensure_ascii=False)),
            Combo(nome="Combo Solo",
                  descricao="1 pizza grande + 1 refrigerante lata",
                  desconto=5.0, ativo=True,
                  itens_json=json.dumps([
                      {"tipo":"Pizza","nome":"Pizza Grande","preco":45.0,"quantidade":1},
                      {"tipo":"Bebida","nome":"Refrigerante Lata","preco":6.0,"quantidade":1},
                  ], ensure_ascii=False)),
        ]
        for c in combos_iniciais:
            combos_repo.adicionar(c)


with app.app_context():
    _seed_cardapio()


@app.context_processor
def injetar_alertas_estoque():
    if 'usuario' not in session:
        return {}
    try:
        alertas = estoque_repo.alertas()
        return {'estoque_alertas': len(alertas),
                'estoque_alertas_lista': alertas[:5]}
    except Exception:
        return {'estoque_alertas': 0, 'estoque_alertas_lista': []}


@app.route('/idioma/<lang>')
def mudar_idioma(lang):
    if lang in SUPPORTED_LANGS:
        session['lang'] = lang
    return redirect(request.referrer or url_for('dashboard'))


# ═════════════════════════════════════════════════════════════
#                        LOGIN / CADASTRO
# ═════════════════════════════════════════════════════════════
@app.route('/', methods=['GET', 'POST'])
@limiter.limit('10 per minute', methods=['POST'], error_message='login_erro_tentativas')
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        senha   = request.form.get('senha', '').strip()

        usuario_valido = usuarios_repo.buscar_por_login(usuario, senha)
        if usuario_valido:
            session['usuario'] = usuario_valido.usuario
            return redirect(url_for('dashboard'))
        flash('Usuário ou senha incorretos.', 'danger')
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/cadastrar_funcionario', methods=['GET', 'POST'])
def cadastrar_funcionario():
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        senha   = request.form.get('senha', '').strip()
        cpf_raw = request.form.get('cpf', '').strip()
        email   = request.form.get('email', '').strip()

        erros = []

        if not usuario or not senha or not cpf_raw or not email:
            erros.append('Preencha todos os campos.')

        if cpf_raw and not validar_cpf(cpf_raw):
            erros.append('CPF inválido. Verifique os dígitos informados.')

        if email and not validar_email(email):
            erros.append('E-mail inválido. Verifique o endereço informado.')

        if not erros:
            if usuarios_repo.existe(usuario):
                erros.append('Este nome de usuário já está em uso.')
            if usuarios_repo.existe_cpf(cpf_raw):
                erros.append('Já existe um funcionário cadastrado com este CPF.')
            if usuarios_repo.existe_email(email):
                erros.append('Já existe um funcionário cadastrado com este e-mail.')

        if erros:
            for e in erros:
                flash(e, 'danger')
            return render_template('cadastrar_funcionario.html',
                                   form_usuario=usuario, form_email=email,
                                   form_cpf=cpf_raw)

        cpf_formatado = formatar_cpf(cpf_raw)
        usuarios_repo.adicionar(Usuario(usuario=usuario, senha=senha,
                                        cpf=cpf_formatado, email=email))
        flash('Cadastro realizado com sucesso! Faça o login.', 'success')
        return redirect(url_for('login'))

    return render_template('cadastrar_funcionario.html',
                           form_usuario='', form_email='', form_cpf='')


@app.route('/logout')
def logout():
    session.pop('usuario', None)
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))


# ═════════════════════════════════════════════════════════════
#                        DASHBOARD
# ═════════════════════════════════════════════════════════════
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if login_obrigatorio():
        flash('Por favor, faça o login primeiro.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        return _processar_novo_pedido()

    pedidos = pedidos_repo.listar()
    clientes = clientes_repo.listar()

    return render_template(
        'dashboard.html',
        vendas=pedidos,
        clientes=clientes,
        usuario_atual=session['usuario'],
        cardapio_pizzas=produtos_repo.dict_pizzas_para_template(apenas_ativas=True),
        cardapio_bebidas=produtos_repo.dict_bebidas_para_template(apenas_ativas=True),
        adicionais=[a.to_dict() for a in adicionais_repo.listar(apenas_ativos=True)],
        combos=[c.to_dict() for c in combos_repo.listar(apenas_ativos=True)],
    )


def _processar_novo_pedido():
    cliente_identificador = request.form.get('cliente', '').strip()
    tipo_entrega    = request.form.get('tipo_entrega')
    endereco        = request.form.get('endereco', '').strip()
    taxa_entrega    = float(request.form.get('taxa_entrega') or 0.0)
    forma_pagamento = request.form.get('forma_pagamento')
    observacoes     = request.form.get('observacoes', '').strip()
    combo_id_raw    = request.form.get('combo_id')
    combo_desconto  = float(request.form.get('combo_desconto') or 0.0)

    itens_json = request.form.get('itens_pedido_json')
    try:
        itens_brutos = json.loads(itens_json) if itens_json else []
    except json.JSONDecodeError:
        itens_brutos = []

    if not itens_brutos:
        flash('Adicione pelo menos um item ao pedido!', 'danger')
        return redirect(url_for('dashboard'))

    # Constrói os DTOs (leves, só pra checagem de estoque e montagem)
    itens_dto = [ItemPedidoDTO.from_dict(i) for i in itens_brutos]

    problemas = estoque_repo.verificar_disponibilidade(itens_dto)
    if problemas:
        for p in problemas:
            flash(f"Sem estoque: {p['nome']} (disponível: {p['disponivel']:g})", 'danger')
        return redirect(url_for('dashboard'))

    cliente_encontrado = clientes_repo.buscar(cliente_identificador)
    teve_desconto = cliente_encontrado is not None
    nome_cliente  = cliente_encontrado.nome if cliente_encontrado else cliente_identificador or '—'

    # Cria o Pedido ORM
    novo_pedido = Pedido(
        atendente=session['usuario'],
        cliente=nome_cliente,
        tipo_entrega=tipo_entrega,
        endereco=endereco if tipo_entrega == 'Entrega' else '',
        taxa_entrega=taxa_entrega if tipo_entrega == 'Entrega' else 0.0,
        forma_pagamento=forma_pagamento,
        teve_desconto=teve_desconto,
        observacoes=observacoes,
        combo_id=int(combo_id_raw) if combo_id_raw else None,
        combo_desconto=combo_desconto,
        data=datetime.now().strftime('%Y-%m-%d'),
        status=Pedido.STATUS_PENDENTE,
    )

    # Salva pedido + itens via repositório (que já faz o refresh)
    pedido_salvo = pedidos_repo.adicionar(novo_pedido, itens_dto)

    # Baixa no estoque (usa o objeto já recarregado com os itens)
    estoque_repo.baixar_por_pedido(pedido_salvo, usuario=session['usuario'])

    msg = f"Pedido #{pedido_salvo.id} registrado!"
    if teve_desconto:
        msg += " (10% de desconto aplicado)."
    if combo_desconto > 0:
        msg += f" (Combo com R$ {combo_desconto:.2f} de desconto)."
    flash(msg, 'success')
    return redirect(url_for('dashboard'))


@app.route('/cadastrar_cliente', methods=['POST'])
def cadastrar_cliente():
    if login_obrigatorio():
        return redirect(url_for('login'))

    nome     = request.form.get('nome_cliente', '').strip()
    cpf_raw  = request.form.get('cpf_cliente', '').strip()
    tel_raw  = request.form.get('telefone_cliente', '').strip()

    erros = []
    if not nome:
        erros.append('Informe o nome do cliente.')
    if not cpf_raw and not tel_raw:
        erros.append('Informe ao menos o CPF ou o telefone do cliente.')
    if cpf_raw and not validar_cpf(cpf_raw):
        erros.append('CPF inválido. Verifique os dígitos informados.')
    if tel_raw and not validar_telefone(tel_raw):
        erros.append('Telefone inválido. Use o formato (11) 91234-5678 ou (11) 3456-7890.')

    if erros:
        for e in erros:
            flash(e, 'danger')
        return redirect(url_for('dashboard'))

    cpf_fmt = formatar_cpf(cpf_raw) if cpf_raw else ''
    tel_fmt = formatar_telefone(tel_raw) if tel_raw else ''

    if cpf_fmt and clientes_repo.existe_cpf(cpf_fmt):
        flash('Já existe um cliente cadastrado com esse CPF!', 'danger')
        return redirect(url_for('dashboard'))
    if tel_fmt and clientes_repo.existe_telefone(tel_fmt):
        flash('Já existe um cliente cadastrado com esse telefone!', 'danger')
        return redirect(url_for('dashboard'))

    clientes_repo.adicionar(Cliente(nome=nome, cpf=cpf_fmt, telefone=tel_fmt))
    flash(f'Cliente {nome} cadastrado! Ele tem 10% de desconto.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/atualizar_status/<int:venda_id>', methods=['POST'])
def atualizar_status(venda_id):
    if login_obrigatorio():
        return redirect(url_for('login'))

    pedido, mudou = pedidos_repo.atualizar_status(venda_id)

    if not pedido:
        flash('Pedido não encontrado.', 'danger')
        return redirect(url_for('dashboard'))

    if not mudou:
        flash(f'Pedido #{venda_id} já foi finalizado!', 'warning')
        return redirect(url_for('dashboard'))

    if pedido.status == Pedido.STATUS_NO_FORNO:
        flash(f'Pedido #{venda_id} movido para o forno!', 'info')
        return redirect(url_for('dashboard'))

    flash(f'Pedido #{venda_id} está pronto!', 'success')
    return redirect(url_for('dashboard'))


# ═════════════════════════════════════════════════════════════
#                        PRODUTOS
# ═════════════════════════════════════════════════════════════
@app.route('/produtos')
def produtos():
    if login_obrigatorio():
        return redirect(url_for('login'))

    estoque_map = {p['id']: p for p in estoque_repo.listar_com_produtos()}
    return render_template(
        'produtos.html',
        pizzas=produtos_repo.listar_pizzas(),
        bebidas=produtos_repo.listar_bebidas(),
        tamanhos=Pizza.TAMANHOS,
        estoque_map=estoque_map,
        usuario_atual=session['usuario'],
    )


@app.route('/produtos/nova_pizza', methods=['POST'])
def nova_pizza():
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))

    nome = request.form.get('nome', '').strip()
    if not nome:
        flash('Informe o nome da pizza.', 'danger')
        return redirect(url_for('produtos'))

    precos = {}
    for tamanho in Pizza.TAMANHOS:
        valor = request.form.get(f'preco_{tamanho}', '0').replace(',', '.')
        try:
            precos[tamanho] = float(valor)
        except ValueError:
            precos[tamanho] = 0.0

    if all(v <= 0 for v in precos.values()):
        flash('Informe ao menos um preço válido.', 'danger')
        return redirect(url_for('produtos'))

    produtos_repo.adicionar(Pizza(nome=nome, precos=precos))
    flash(f'Pizza "{nome}" adicionada ao cardápio!', 'success')
    return redirect(url_for('produtos'))


@app.route('/produtos/nova_bebida', methods=['POST'])
def nova_bebida():
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))

    nome = request.form.get('nome', '').strip()
    try:
        preco = float(request.form.get('preco', '0').replace(',', '.'))
    except ValueError:
        preco = 0.0

    if not nome or preco <= 0:
        flash('Informe nome e preço válidos.', 'danger')
        return redirect(url_for('produtos'))

    produtos_repo.adicionar(Bebida(nome=nome, preco=preco))
    flash(f'Bebida "{nome}" adicionada ao cardápio!', 'success')
    return redirect(url_for('produtos'))


@app.route('/produtos/alternar/<int:produto_id>', methods=['POST'])
def alternar_produto(produto_id):
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))

    produto = produtos_repo.alternar_status(produto_id)
    if not produto:
        flash('Produto não encontrado.', 'danger')
    else:
        estado = "habilitado" if produto.ativo else "desabilitado"
        flash(f'"{produto.nome}" {estado} com sucesso!', 'success')

    return redirect(url_for('produtos'))


@app.route('/cancelar_pedido/<int:venda_id>', methods=['POST'])
def cancelar_pedido(venda_id):
    if login_obrigatorio():
        return redirect(url_for('login'))
    motivo = request.form.get('motivo_cancelamento', '').strip()
    pedido, cancelou = pedidos_repo.cancelar(venda_id, motivo)
    if not pedido:
        flash('Pedido não encontrado.', 'danger')
    elif not cancelou:
        flash(f'Pedido #{venda_id} não pode ser cancelado (já está pronto).', 'warning')
    else:
        flash(f'Pedido #{venda_id} cancelado.', 'info')
    return redirect(url_for('dashboard'))


@app.route('/cliente/<path:nome>/historico')
def historico_cliente(nome):
    if login_obrigatorio():
        return redirect(url_for('login'))
    pedidos = pedidos_repo.historico_cliente(nome)
    return render_template('historico_cliente.html',
                           nome_cliente=nome,
                           pedidos=pedidos,
                           usuario_atual=session['usuario'])


@app.route('/pedido/<int:venda_id>/comanda')
def comanda(venda_id):
    if login_obrigatorio():
        return redirect(url_for('login'))
    pedido = pedidos_repo.buscar_por_id(venda_id)
    if not pedido:
        flash('Pedido não encontrado.', 'danger')
        return redirect(url_for('dashboard'))
    return render_template('comanda.html', pedido=pedido)


# ═════════════════════════════════════════════════════════════
#                        DELIVERY
# ═════════════════════════════════════════════════════════════
@app.route('/entrega/<int:venda_id>')
def rastreio_entrega(venda_id):
    pedido = pedidos_repo.buscar_por_id(venda_id)
    if not pedido or pedido.tipo_entrega != 'Entrega':
        return render_template('rastreio.html', pedido=None), 404
    return render_template('rastreio.html', pedido=pedido)


@app.route('/entrega/<int:venda_id>/avancar', methods=['POST'])
def avancar_entrega(venda_id):
    if login_obrigatorio():
        return redirect(url_for('login'))
    motoboy = request.form.get('motoboy', '').strip()
    pedido, mudou = pedidos_repo.atualizar_entrega(venda_id, motoboy)
    if not pedido:
        flash('Pedido não encontrado.', 'danger')
    elif not mudou:
        flash('Não foi possível avançar a entrega.', 'warning')
    else:
        if pedido.entrega_status == Pedido.ENTREGA_SAIU:
            flash(f'Pedido #{venda_id} saiu para entrega!', 'info')
        else:
            flash(f'Pedido #{venda_id} entregue!', 'success')
    return redirect(url_for('dashboard'))


# ═════════════════════════════════════════════════════════════
#                        COMBOS
# ═════════════════════════════════════════════════════════════
@app.route('/combos')
def combos():
    if login_obrigatorio():
        return redirect(url_for('login'))
    return render_template(
        'combos.html',
        combos=combos_repo.listar(),
        cardapio_pizzas=produtos_repo.dict_pizzas_para_template(apenas_ativas=True),
        cardapio_bebidas=produtos_repo.dict_bebidas_para_template(apenas_ativas=True),
        usuario_atual=session['usuario'],
    )


@app.route('/combos/novo', methods=['POST'])
def novo_combo():
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))
    nome = request.form.get('nome', '').strip()
    descricao = request.form.get('descricao', '').strip()
    try:
        desconto = float(request.form.get('desconto', '0').replace(',', '.'))
    except ValueError:
        desconto = 0.0
    itens_json = request.form.get('itens_json', '[]')
    try:
        itens = json.loads(itens_json)
    except json.JSONDecodeError:
        itens = []

    if not nome or not itens:
        flash('Informe nome e pelo menos 1 item no combo.', 'danger')
        return redirect(url_for('combos'))

    combos_repo.adicionar(Combo(
        nome=nome, descricao=descricao, desconto=desconto, ativo=True,
        itens_json=json.dumps(itens, ensure_ascii=False)))
    flash(f'Combo "{nome}" criado!', 'success')
    return redirect(url_for('combos'))


@app.route('/combos/alternar/<int:combo_id>', methods=['POST'])
def alternar_combo(combo_id):
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))
    c = combos_repo.alternar_status(combo_id)
    if c:
        flash(f'Combo "{c.nome}" {"ativado" if c.ativo else "desativado"}.', 'success')
    return redirect(url_for('combos'))


@app.route('/combos/remover/<int:combo_id>', methods=['POST'])
def remover_combo(combo_id):
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))
    combos_repo.remover(combo_id)
    flash('Combo removido.', 'info')
    return redirect(url_for('combos'))


# ═════════════════════════════════════════════════════════════
#                        ADICIONAIS
# ═════════════════════════════════════════════════════════════
@app.route('/adicionais')
def adicionais():
    if login_obrigatorio():
        return redirect(url_for('login'))
    return render_template(
        'adicionais.html',
        adicionais=adicionais_repo.listar(),
        usuario_atual=session['usuario'],
    )


@app.route('/adicionais/novo', methods=['POST'])
def novo_adicional():
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))
    nome = request.form.get('nome', '').strip()
    try:
        preco = float(request.form.get('preco', '0').replace(',', '.'))
    except ValueError:
        preco = 0.0
    aplica = request.form.get('aplica', 'ambos')
    if not nome or preco <= 0:
        flash('Informe nome e preço válidos.', 'danger')
        return redirect(url_for('adicionais'))
    adicionais_repo.adicionar(Adicional(nome=nome, preco=preco,
                                        ativo=True, aplica=aplica))
    flash(f'Adicional "{nome}" criado!', 'success')
    return redirect(url_for('adicionais'))


@app.route('/adicionais/alternar/<int:adic_id>', methods=['POST'])
def alternar_adicional(adic_id):
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))
    a = adicionais_repo.alternar_status(adic_id)
    if a:
        flash(f'"{a.nome}" {"ativado" if a.ativo else "desativado"}.', 'success')
    return redirect(url_for('adicionais'))


@app.route('/adicionais/remover/<int:adic_id>', methods=['POST'])
def remover_adicional(adic_id):
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))
    adicionais_repo.remover(adic_id)
    flash('Adicional removido.', 'info')
    return redirect(url_for('adicionais'))


# ═════════════════════════════════════════════════════════════
#                        ESTOQUE
# ═════════════════════════════════════════════════════════════
@app.route('/estoque')
def estoque():
    if login_obrigatorio():
        return redirect(url_for('login'))
    produtos_estoque = estoque_repo.listar_com_produtos()
    movimentacoes = estoque_repo.listar_movimentacoes(limite=50)
    return render_template(
        'estoque.html',
        produtos=produtos_estoque,
        movimentacoes=movimentacoes,
        fornecedores_view=fornecedores_repo.listar(apenas_ativos=True),
        usuario_atual=session['usuario'],
    )


@app.route('/estoque/ajustar/<int:produto_id>', methods=['POST'])
def ajustar_estoque(produto_id):
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))

    tipo = request.form.get('tipo', 'entrada')
    try:
        qtd = float(request.form.get('quantidade', '0').replace(',', '.'))
    except ValueError:
        flash('Quantidade inválida.', 'danger')
        return redirect(url_for('estoque'))

    motivo = request.form.get('motivo', '').strip()
    fornecedor = request.form.get('fornecedor', '').strip()
    try:
        preco = float(request.form.get('preco_unitario', '0').replace(',', '.'))
    except ValueError:
        preco = 0.0

    if qtd <= 0:
        flash('Quantidade deve ser maior que zero.', 'danger')
        return redirect(url_for('estoque'))

    mov = MovimentacaoEstoque(
        produto_id=produto_id, tipo=tipo, quantidade=qtd,
        motivo=motivo, fornecedor=fornecedor, preco_unitario=preco,
        usuario=session['usuario'],
        data=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    estoque_repo.registrar_movimentacao(mov)
    flash(f'Estoque atualizado ({tipo}: {qtd:g}).', 'success')
    return redirect(url_for('estoque'))


@app.route('/estoque/minimo/<int:produto_id>', methods=['POST'])
def definir_minimo_estoque(produto_id):
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))
    try:
        minimo = float(request.form.get('minimo', '5').replace(',', '.'))
    except ValueError:
        minimo = 5.0
    unidade = request.form.get('unidade', 'un').strip() or 'un'
    estoque_repo.definir_minimo(produto_id, minimo, unidade)
    flash('Mínimo atualizado.', 'success')
    return redirect(url_for('estoque'))


# ═════════════════════════════════════════════════════════════
#                        COMPRAS
# ═════════════════════════════════════════════════════════════
@app.route('/compras')
def compras():
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))

    data_inicio = request.args.get('data_inicio', '')
    data_fim    = request.args.get('data_fim', '')
    fornecedor_filtro = request.args.get('fornecedor_id', '')

    movs = estoque_repo.listar_movimentacoes(tipo='entrada', limite=300)
    if data_inicio:
        movs = [m for m in movs if m['data'][:10] >= data_inicio]
    if data_fim:
        movs = [m for m in movs if m['data'][:10] <= data_fim]
    if fornecedor_filtro:
        movs = [m for m in movs if str(m.get('fornecedor_id')) == fornecedor_filtro]

    resumo = estoque_repo.resumo_compras(data_inicio or None, data_fim or None)

    return render_template(
        'compras.html',
        movimentacoes=movs,
        resumo=resumo,
        produtos=estoque_repo.listar_com_produtos(),
        fornecedores=fornecedores_repo.listar(apenas_ativos=True),
        data_inicio=data_inicio,
        data_fim=data_fim,
        fornecedor_filtro=fornecedor_filtro,
        usuario_atual=session['usuario'],
    )


@app.route('/compras/nova', methods=['POST'])
def nova_compra():
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))

    fornecedor_id = request.form.get('fornecedor_id')
    fornecedor_nome = request.form.get('fornecedor_nome', '').strip()
    itens_json = request.form.get('itens_json', '[]')
    try:
        itens = json.loads(itens_json)
    except json.JSONDecodeError:
        itens = []

    if not itens:
        flash('Adicione pelo menos 1 item na compra.', 'danger')
        return redirect(url_for('compras'))

    fornecedor_id_int = int(fornecedor_id) if fornecedor_id else None
    if fornecedor_id_int:
        f_obj = fornecedores_repo.buscar_por_id(fornecedor_id_int)
        if f_obj:
            fornecedor_nome = f_obj.nome

    total = 0.0
    itens_ok = 0
    for it in itens:
        try:
            produto_id = int(it['produto_id'])
            quantidade = float(it['quantidade'])
            preco      = float(it.get('preco_unitario', 0))
        except (KeyError, ValueError, TypeError):
            continue
        if quantidade <= 0:
            continue
        mov = MovimentacaoEstoque(
            produto_id=produto_id, tipo='entrada',
            quantidade=quantidade,
            motivo='Compra de fornecedor',
            fornecedor=fornecedor_nome,
            fornecedor_id=fornecedor_id_int,
            preco_unitario=preco,
            usuario=session['usuario'],
            data=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        estoque_repo.registrar_movimentacao(mov)
        total += quantidade * preco
        itens_ok += 1

    if itens_ok == 0:
        flash('Nenhum item válido na compra.', 'danger')
        return redirect(url_for('compras'))

    flash(f'Compra registrada! {itens_ok} item(ns) — Total: R$ {total:.2f}', 'success')
    return redirect(url_for('compras'))


@app.route('/compras/fardo', methods=['POST'])
def compra_fardo():
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))

    try:
        produto_id         = int(request.form.get('produto_id'))
        unidades_por_fardo = float(request.form.get('unidades_por_fardo', '0').replace(',', '.'))
        qtd_fardos         = float(request.form.get('qtd_fardos', '0').replace(',', '.'))
        preco_fardo        = float(request.form.get('preco_fardo', '0').replace(',', '.'))
    except (ValueError, TypeError):
        flash('Valores inválidos na compra.', 'danger')
        return redirect(url_for('estoque'))

    if unidades_por_fardo <= 0 or unidades_por_fardo > 1000:
        flash('Unidades por fardo inválido (1 a 1000).', 'danger')
        return redirect(url_for('estoque'))
    if qtd_fardos <= 0 or qtd_fardos > 500:
        flash('Quantidade de fardos inválida (1 a 500).', 'danger')
        return redirect(url_for('estoque'))
    if preco_fardo < 0 or preco_fardo > 100000:
        flash('Preço do fardo inválido.', 'danger')
        return redirect(url_for('estoque'))

    fornecedor_id = request.form.get('fornecedor_id')
    fornecedor_id_int = int(fornecedor_id) if fornecedor_id else None
    fornecedor_nome = ''
    if fornecedor_id_int:
        f_obj = fornecedores_repo.buscar_por_id(fornecedor_id_int)
        if f_obj:
            fornecedor_nome = f_obj.nome

    total_unidades = unidades_por_fardo * qtd_fardos
    preco_unit = preco_fardo / unidades_por_fardo if unidades_por_fardo > 0 else 0

    mov = MovimentacaoEstoque(
        produto_id=produto_id, tipo='entrada',
        quantidade=total_unidades,
        motivo=f'Fardo ({qtd_fardos:g}x {unidades_por_fardo:g} un)',
        fornecedor=fornecedor_nome,
        fornecedor_id=fornecedor_id_int,
        preco_unitario=preco_unit,
        usuario=session['usuario'],
        data=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    estoque_repo.registrar_movimentacao(mov)

    flash(f'Fardo registrado! +{total_unidades:g} un — R$ {preco_fardo*qtd_fardos:.2f}', 'success')
    return redirect(url_for('estoque'))


# ═════════════════════════════════════════════════════════════
#                        FORNECEDORES
# ═════════════════════════════════════════════════════════════
@app.route('/fornecedores')
def fornecedores():
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))
    return render_template(
        'fornecedores.html',
        fornecedores=fornecedores_repo.listar(),
        usuario_atual=session['usuario'],
    )


@app.route('/fornecedores/novo', methods=['POST'])
def novo_fornecedor():
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))

    nome = request.form.get('nome', '').strip()
    if not nome:
        flash('Informe o nome do fornecedor.', 'danger')
        return redirect(url_for('fornecedores'))

    cnpj_raw = request.form.get('cnpj', '').strip()
    if cnpj_raw and not validar_cnpj(cnpj_raw):
        flash('CNPJ inválido. Verifique os dígitos informados.', 'danger')
        return redirect(url_for('fornecedores'))

    cnpj_fmt = formatar_cnpj(cnpj_raw) if cnpj_raw else ''

    f = Fornecedor(
        nome=nome, cnpj=cnpj_fmt,
        telefone=request.form.get('telefone', '').strip(),
        email=request.form.get('email', '').strip(),
        endereco=request.form.get('endereco', '').strip(),
        obs=request.form.get('obs', '').strip(),
        ativo=True)
    fornecedores_repo.adicionar(f)
    flash(f'Fornecedor "{nome}" cadastrado!', 'success')
    return redirect(url_for('fornecedores'))


@app.route('/fornecedores/editar/<int:f_id>', methods=['POST'])
def editar_fornecedor(f_id):
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))

    cnpj_raw = request.form.get('cnpj', '').strip()
    if cnpj_raw and not validar_cnpj(cnpj_raw):
        flash('CNPJ inválido. Verifique os dígitos informados.', 'danger')
        return redirect(url_for('fornecedores'))

    dados = {
        'nome':     request.form.get('nome', '').strip(),
        'cnpj':     formatar_cnpj(cnpj_raw) if cnpj_raw else '',
        'telefone': request.form.get('telefone', '').strip(),
        'email':    request.form.get('email', '').strip(),
        'endereco': request.form.get('endereco', '').strip(),
        'obs':      request.form.get('obs', '').strip(),
    }
    if not dados['nome']:
        flash('Informe o nome.', 'danger')
        return redirect(url_for('fornecedores'))
    fornecedores_repo.atualizar(f_id, dados)
    flash('Fornecedor atualizado!', 'success')
    return redirect(url_for('fornecedores'))


@app.route('/fornecedores/alternar/<int:f_id>', methods=['POST'])
def alternar_fornecedor(f_id):
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))
    f = fornecedores_repo.alternar_status(f_id)
    if f:
        flash(f'"{f.nome}" {"ativado" if f.ativo else "desativado"}.', 'success')
    return redirect(url_for('fornecedores'))


@app.route('/fornecedores/remover/<int:f_id>', methods=['POST'])
def remover_fornecedor(f_id):
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))
    fornecedores_repo.remover(f_id)
    flash('Fornecedor removido.', 'info')
    return redirect(url_for('fornecedores'))


@app.route('/fornecedores/<int:f_id>/historico')
def historico_fornecedor(f_id):
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))
    f = fornecedores_repo.buscar_por_id(f_id)
    if not f:
        flash('Fornecedor não encontrado.', 'danger')
        return redirect(url_for('fornecedores'))
    movs = fornecedores_repo.historico_compras(f_id)
    total = sum(m['quantidade'] * m['preco_unitario'] for m in movs)
    return render_template(
        'historico_fornecedor.html',
        fornecedor=f,
        movimentacoes=movs,
        total=total,
        usuario_atual=session['usuario'],
    )


# ═════════════════════════════════════════════════════════════
#                        USUÁRIOS
# ═════════════════════════════════════════════════════════════
@app.route('/usuarios')
def usuarios():
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))
    return render_template(
        'usuarios.html',
        usuarios=usuarios_repo.listar(),
        meu_usuario=session['usuario'],
        usuario_atual=session['usuario'],
    )


@app.route('/usuarios/perfil/<path:usuario>', methods=['POST'])
def alterar_perfil(usuario):
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))

    novo = request.form.get('perfil', '').strip()
    if novo not in ('funcionario', 'gerente'):
        flash('Perfil inválido.', 'danger')
        return redirect(url_for('usuarios'))

    if usuario == session['usuario'] and novo != 'gerente':
        if usuarios_repo.contar_gerentes() <= 1:
            flash('Você é o único gerente. Promova outro antes de mudar seu perfil.', 'warning')
            return redirect(url_for('usuarios'))

    usuarios_repo.definir_perfil(usuario, novo)
    flash(f'Perfil de "{usuario}" alterado para {novo}.', 'success')
    return redirect(url_for('usuarios'))


@app.route('/usuarios/remover/<path:usuario>', methods=['POST'])
def remover_usuario(usuario):
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))

    if usuario == session['usuario']:
        flash('Você não pode remover a si mesmo.', 'warning')
        return redirect(url_for('usuarios'))

    u = usuarios_repo.buscar_por_nome(usuario)
    if u and u.is_gerente and usuarios_repo.contar_gerentes() <= 1:
        flash('Não é possível remover o último gerente.', 'warning')
        return redirect(url_for('usuarios'))

    usuarios_repo.remover(usuario)
    flash(f'Usuário "{usuario}" removido.', 'info')
    return redirect(url_for('usuarios'))


# ═════════════════════════════════════════════════════════════
#                        CAIXA
# ═════════════════════════════════════════════════════════════
@app.route('/fechar_caixa', methods=['POST'])
def fechar_caixa():
    if login_obrigatorio():
        return redirect(url_for('login'))

    pedidos = pedidos_repo.listar()
    if not pedidos:
        flash('Fila vazia. Não há vendas para fechar.', 'warning')
        return redirect(url_for('dashboard'))

    # Só pedidos não cancelados
    ativos = [p for p in pedidos if p.status != Pedido.STATUS_CANCELADO]
    faturamento_total = sum((p.preco_final or 0.0) for p in ativos)

    # Resumo por forma de pagamento
    resumo = {forma: 0.0 for forma in FechamentoCaixa.FORMAS_PAGAMENTO_PADRAO}
    for p in ativos:
        forma = p.forma_pagamento or 'Dinheiro'
        resumo[forma] = resumo.get(forma, 0.0) + (p.preco_final or 0.0)

    # Itens arquivados (todos os itens dos pedidos)
    itens_arquivados = []
    for p in pedidos:
        for item in p.itens:
            itens_arquivados.append({
                'tipo': item.tipo,
                'nome': item.nome,
                'preco': item.preco,
                'quantidade': item.quantidade,
            })

    fechamento = FechamentoCaixa(
        usuario=session['usuario'],
        data_fechamento=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        total_vendas=len(ativos),
        faturamento_total=faturamento_total,
    )
    caixa_repo.adicionar(fechamento,
                         resumo_pagamentos=resumo,
                         itens_arquivados=itens_arquivados)

    pedidos_repo.limpar()

    session['ultimo_caixa_id'] = fechamento.id
    flash(f'Caixa fechado! Faturamento: R$ {faturamento_total:.2f}', 'success')
    return redirect(url_for('relatorios'))


@app.route('/caixa/<int:caixa_id>/pdf')
def gerar_pdf_caixa(caixa_id):
    if login_obrigatorio():
        return redirect(url_for('login'))

    fechamento = next((f for f in caixa_repo.listar() if f.id == caixa_id), None)
    if not fechamento:
        flash('Fechamento não encontrado.', 'danger')
        return redirect(url_for('relatorios'))

    pdf_buffer = RelatorioCaixaPDF(fechamento).gerar()
    return send_file(pdf_buffer, as_attachment=True,
                     download_name=f'fechamento_caixa_{caixa_id}.pdf',
                     mimetype='application/pdf')


# ═════════════════════════════════════════════════════════════
#                        RELATÓRIOS
# ═════════════════════════════════════════════════════════════
@app.route('/relatorios')
def relatorios():
    if gerente_obrigatorio():
        return redirect(url_for('dashboard'))

    hoje_str = datetime.now().strftime('%Y-%m-%d')
    data_inicio = request.args.get('data_inicio', '') or hoje_str
    data_fim    = request.args.get('data_fim',    '') or hoje_str

    pedidos_atuais   = pedidos_repo.listar()
    historico_caixas = caixa_repo.listar()

    pedidos_periodo = pedidos_repo.listar_por_periodo(data_inicio, data_fim)

    caixas_no_periodo = []
    for c in historico_caixas:
        ds = c.data_fechamento.split(' ')[0]
        if data_inicio <= ds <= data_fim:
            caixas_no_periodo.append(c)

    faturamento_pedidos = sum(p.preco_final for p in pedidos_periodo
                              if p.status != 'Cancelado')
    faturamento_caixas  = sum(c.faturamento_total for c in caixas_no_periodo)
    faturamento_periodo = faturamento_pedidos + faturamento_caixas

    compras_periodo = estoque_repo.resumo_compras(data_inicio, data_fim)
    total_compras   = compras_periodo['total']
    n_compras       = compras_periodo['n_compras']

    lucro_liquido = faturamento_periodo - total_compras
    margem = (lucro_liquido / faturamento_periodo * 100) if faturamento_periodo > 0 else 0.0

    lista_sabores = _coletar_sabores(pedidos_periodo, caixas_no_periodo)

    contagem_sabores = Counter(lista_sabores).most_common(5)
    ranking_sabores  = [{'sabor': s, 'quantidade': q} for s, q in contagem_sabores]

    faturamento_dia, faturamento_semana, faturamento_mes = _calcular_faturamentos(
        pedidos_atuais, historico_caixas
    )

    # ── Ranking de funcionários ──
    vendas_por_funcionario = {}
    for p in pedidos_atuais:
        if p.status == 'Cancelado':
            continue
        if p.atendente not in vendas_por_funcionario:
            vendas_por_funcionario[p.atendente] = {'pedidos': 0, 'faturamento': 0.0}
        vendas_por_funcionario[p.atendente]['pedidos']    += 1
        vendas_por_funcionario[p.atendente]['faturamento'] += p.preco_final
    ranking_funcionarios = sorted(vendas_por_funcionario.items(),
                                  key=lambda x: x[1]['faturamento'], reverse=True)

    # ── max_fat seguro (nunca 0 para evitar ZeroDivisionError) ──
    max_fat = 0.0
    if ranking_funcionarios:
        max_fat = max((dados['faturamento'] for _, dados in ranking_funcionarios),
                      default=0.0) or 0.0

    ultimo_caixa_id = session.pop('ultimo_caixa_id', None)
    ultimo_caixa    = next((f for f in historico_caixas if f.id == ultimo_caixa_id), None)

    detalhe_compras = _detalhar_compras(data_inicio, data_fim)

    caixas_labels = []
    caixas_fat    = []
    caixas_comp   = []
    caixas_lucro  = []
    for c in historico_caixas:
        caixas_labels.append(f'Caixa #{c.id}')
        caixas_fat.append(round(c.faturamento_total, 2))
        ds = c.data_fechamento.split(' ')[0]
        compras_dia = estoque_repo.resumo_compras(ds, ds)
        caixas_comp.append(round(compras_dia['total'], 2))
        caixas_lucro.append(round(c.faturamento_total - compras_dia['total'], 2))

    return render_template(
        'relatorios.html',
        faturamento_dia=faturamento_dia,
        faturamento_semana=faturamento_semana,
        faturamento_mes=faturamento_mes,
        ranking_sabores=ranking_sabores,
        ranking_funcionarios=ranking_funcionarios,
        max_fat=max_fat,
        historico_caixas=historico_caixas,
        ultimo_caixa=ultimo_caixa,
        usuario_atual=session['usuario'],
        data_inicio=data_inicio,
        data_fim=data_fim,
        faturamento_periodo=faturamento_periodo,
        total_compras=total_compras,
        n_compras=n_compras,
        lucro_liquido=lucro_liquido,
        margem=margem,
        detalhe_compras=detalhe_compras,
        caixas_labels=caixas_labels,
        caixas_fat=caixas_fat,
        caixas_comp=caixas_comp,
        caixas_lucro=caixas_lucro,
    )


def _detalhar_compras(data_inicio, data_fim):
    movs = estoque_repo.listar_movimentacoes(tipo='entrada', limite=1000)
    if data_inicio:
        movs = [m for m in movs if m['data'][:10] >= data_inicio]
    if data_fim:
        movs = [m for m in movs if m['data'][:10] <= data_fim]

    por_fornecedor = {}
    for m in movs:
        fornecedor = m.get('fornecedor') or 'Sem fornecedor'
        valor = m['quantidade'] * m['preco_unitario']
        if fornecedor not in por_fornecedor:
            por_fornecedor[fornecedor] = {'total': 0.0, 'n': 0}
        por_fornecedor[fornecedor]['total'] += valor
        por_fornecedor[fornecedor]['n']     += 1

    return sorted(
        [{'fornecedor': k, **v} for k, v in por_fornecedor.items()],
        key=lambda x: x['total'], reverse=True
    )


def _coletar_sabores(pedidos_atuais, historico_caixas):
    sabores = []

    def extrair(itens):
        for item in itens:
            tipo = item.tipo if hasattr(item, 'tipo') else item.get('tipo')
            nome = item.nome if hasattr(item, 'nome') else item.get('nome')
            qtd  = item.quantidade if hasattr(item, 'quantidade') else item.get('quantidade', 1)
            if tipo == 'Pizza':
                base = nome.split(' (')[0]
                partes = [p.strip() for p in base.split('+')]
                for parte in partes:
                    sabores.extend([parte] * qtd)

    for p in pedidos_atuais:
        extrair(p.itens)
    for c in historico_caixas:
        extrair(c.itens_arquivados)

    return sabores


def _calcular_faturamentos(pedidos_atuais, historico_caixas):
    hoje             = datetime.now()
    data_hoje_str    = hoje.strftime('%Y-%m-%d')
    sete_dias_atras  = hoje - timedelta(days=7)
    primeiro_dia_mes = hoje.replace(day=1)

    fd = fs = fm = 0.0

    for p in pedidos_atuais:
        if not p.data:
            continue
        dp = datetime.strptime(p.data, '%Y-%m-%d')
        v  = p.preco_final
        if p.data == data_hoje_str:   fd += v
        if dp >= sete_dias_atras:     fs += v
        if dp >= primeiro_dia_mes:    fm += v

    for c in historico_caixas:
        ds  = c.data_fechamento.split(' ')[0]
        dc  = datetime.strptime(ds, '%Y-%m-%d')
        v   = c.faturamento_total
        if ds == data_hoje_str:   fd += v
        if dc >= sete_dias_atras: fs += v
        if dc >= primeiro_dia_mes: fm += v

    return fd, fs, fm


# ═════════════════════════════════════════════════════════════
#                        PDF (comprovante)
# ═════════════════════════════════════════════════════════════
@app.route('/nota/<int:venda_id>')
def gerar_nota(venda_id):
    if login_obrigatorio():
        return redirect(url_for('login'))

    pedido = pedidos_repo.buscar_por_id(venda_id)
    if not pedido:
        flash('Pedido não encontrado.', 'danger')
        return redirect(url_for('dashboard'))

    pdf_buffer = ComprovantePDF(pedido).gerar()
    return send_file(pdf_buffer, as_attachment=True,
                     download_name=f'pedido_{venda_id}.pdf',
                     mimetype='application/pdf')


# ═════════════════════════════════════════════════════════════
#                        CONFIGURAÇÕES
# ═════════════════════════════════════════════════════════════
@app.route('/configuracoes/salvar', methods=['POST'])
def salvar_configuracoes():
    if login_obrigatorio():
        return {'ok': False}, 401
    data = request.get_json(silent=True) or {}
    chave = data.get('chave')
    valor = data.get('valor')
    if chave in ('cfg_taxa_entrega', 'cfg_pagamento'):
        session[chave] = valor
    return {'ok': True}


if __name__ == '__main__':
    app.run(debug=True)