# -*- coding: utf-8 -*-
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


class ComprovantePDF:
    COR_PRIMARIA       = colors.HexColor("#C0392B")
    COR_PRIMARIA_ESCURA= colors.HexColor("#7B241C")
    COR_TEXTO          = colors.HexColor("#222222")
    COR_TEXTO_SUAVE    = colors.HexColor("#6c6c6c")
    COR_LINHA          = colors.HexColor("#e0e0e0")
    COR_FAIXA          = colors.HexColor("#FBEAEA")
    COR_ZEBRA          = colors.HexColor("#F7F7F7")

    # Altura de cada linha da tabela — rect e avanço de y usam o MESMO valor
    ALTURA_LINHA = 22

    def __init__(self, pedido):
        self.pedido = pedido
        self.pagina_largura, self.pagina_altura = A4
        self.margem = 18 * mm
        self.y = 0
        self.pdf = None

    def gerar(self):
        buffer = BytesIO()
        self.pdf = canvas.Canvas(buffer, pagesize=A4)
        self._desenhar_cabecalho()
        self._desenhar_dados_pedido()
        self._desenhar_tabela_itens()
        self._desenhar_resumo_financeiro()
        self._desenhar_rodape()
        self.pdf.save()
        buffer.seek(0)
        return buffer

    # ── Cabeçalho ────────────────────────────────────────────────────
    def _desenhar_cabecalho(self):
        pdf = self.pdf
        largura, altura = self.pagina_largura, self.pagina_altura

        pdf.setFillColor(self.COR_PRIMARIA)
        pdf.rect(0, altura - 95, largura, 95, fill=1, stroke=0)

        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 24)
        pdf.drawString(self.margem, altura - 48, "GB PIZZARIA")

        pdf.setFont("Helvetica", 11)
        pdf.drawString(self.margem, altura - 66, "Comprovante de Pedido")

        pdf.setFont("Helvetica", 9)
        pdf.drawRightString(
            largura - self.margem, altura - 48,
            f"Emitido em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )

        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawRightString(largura - self.margem, altura - 70,
                            f"PEDIDO #{self.pedido.id}")

        self.y = altura - 120

    # ── Dados do pedido ───────────────────────────────────────────────
    def _desenhar_dados_pedido(self):
        pdf = self.pdf
        largura = self.pagina_largura
        altura_caixa = 36 * 3 + 20  # 128pt — 3 linhas de campos + padding

        y_caixa_topo = self.y + 10
        pdf.setFillColor(self.COR_FAIXA)
        pdf.roundRect(self.margem, y_caixa_topo - altura_caixa,
                      largura - 2 * self.margem, altura_caixa, 6, fill=1, stroke=0)

        col1_x = self.margem + 14
        col2_x = largura / 2 + 10
        y_topo  = self.y + 4

        def campo(x, y, rotulo, valor):
            pdf.setFont("Helvetica-Bold", 8.5)
            pdf.setFillColor(self.COR_TEXTO_SUAVE)
            pdf.drawString(x, y, rotulo.upper())
            pdf.setFont("Helvetica-Bold", 11)
            pdf.setFillColor(self.COR_TEXTO)
            pdf.drawString(x, y - 14, valor)

        campo(col1_x, y_topo,       "Cliente",   self.pedido.cliente or "—")
        campo(col2_x, y_topo,       "Data",      self.pedido.data)
        campo(col1_x, y_topo - 36,  "Atendente", self.pedido.atendente)
        campo(col2_x, y_topo - 36,  "Pagamento", self.pedido.forma_pagamento)

        if self.pedido.tipo_entrega == 'Entrega':
            campo(col1_x, y_topo - 72, "Entrega",
                  f"Domicílio — {self.pedido.endereco}")
        else:
            campo(col1_x, y_topo - 72, "Entrega", "Retirada no Balcão")

        self.y = y_caixa_topo - altura_caixa - 16

    # ── Tabela de itens ───────────────────────────────────────────────
    def _desenhar_tabela_itens(self):
        pdf   = self.pdf
        AL    = self.ALTURA_LINHA          # 22pt — único valor usado para rect e avanço
        largura = self.pagina_largura
        x_esq, x_dir = self.margem, largura - self.margem

        self.y -= 12
        pdf.setFont("Helvetica-Bold", 12)
        pdf.setFillColor(self.COR_PRIMARIA_ESCURA)
        pdf.drawString(x_esq, self.y, "ITENS DO PEDIDO")
        self.y -= 16

        # ── Cabeçalho vermelho ──
        ALTURA_HEADER = 20
        pdf.setFillColor(self.COR_PRIMARIA)
        pdf.rect(x_esq, self.y - ALTURA_HEADER, x_dir - x_esq, ALTURA_HEADER,
                 fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 9)
        # Texto centrado verticalmente no header: baseline = topo - 14
        y_header_texto = self.y - ALTURA_HEADER + 7
        pdf.drawString(x_esq + 8,    y_header_texto, "QTD")
        pdf.drawString(x_esq + 50,   y_header_texto, "ITEM")
        pdf.drawRightString(x_dir - 90, y_header_texto, "UNIT.")
        pdf.drawRightString(x_dir - 8,  y_header_texto, "TOTAL")
        self.y -= ALTURA_HEADER + 16  # respiro após o header

        # ── Linhas de itens ──
        pdf.setFont("Helvetica", 10)
        for item in self.pedido.itens:
            adics   = getattr(item, 'adicionais', []) or []
            n_adics = len(adics)

            # Quantas linhas ocupa este item no total
            linhas_extra   = n_adics          # cada adicional ocupa 11pt
            altura_bloco   = AL + n_adics * 11 + (3 if n_adics else 0)

            if self.y - altura_bloco < 110:
                self._nova_pagina_continuacao()
                linha_alt = True

            # ── Texto do item ──
            pdf.setFillColor(self.COR_TEXTO)
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(x_esq + 8, self.y, f"{item.quantidade}x")

            pdf.setFont("Helvetica", 10)
            pdf.drawString(x_esq + 50, self.y, item.nome)
            pdf.drawRightString(x_dir - 90, self.y, f"R$ {item.preco:.2f}")

            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawRightString(x_dir - 8, self.y, f"R$ {item.total:.2f}")

            # ── Adicionais ──
            if n_adics:
                pdf.setFont("Helvetica-Oblique", 8)
                pdf.setFillColor(self.COR_TEXTO_SUAVE)
                for a in adics:
                    self.y -= 11
                    pdf.drawString(x_esq + 50, self.y,
                                   f"  + {a.get('nome','')}  "
                                   f"(R$ {float(a.get('preco',0)):.2f})")
                self.y -= 3

            self.y -= AL

        pdf.setStrokeColor(self.COR_LINHA)
        pdf.line(x_esq, self.y + 6, x_dir, self.y + 6)
        self.y -= 14

    def _nova_pagina_continuacao(self):
        self.pdf.showPage()
        self.y = self.pagina_altura - 60
        self.pdf.setFont("Helvetica-Oblique", 9)
        self.pdf.setFillColor(self.COR_TEXTO_SUAVE)
        self.pdf.drawString(self.margem, self.y,
                            f"Pedido #{self.pedido.id} (continuação)")
        self.y -= 24

    # ── Resumo financeiro ─────────────────────────────────────────────
    def _linha_resumo(self, rotulo, valor, destaque=False):
        pdf   = self.pdf
        x_dir = self.pagina_largura - self.margem
        if destaque:
            pdf.setFont("Helvetica-Bold", 13)
            pdf.setFillColor(self.COR_PRIMARIA_ESCURA)
        else:
            pdf.setFont("Helvetica", 10.5)
            pdf.setFillColor(self.COR_TEXTO_SUAVE)
        pdf.drawString(x_dir - 220, self.y, rotulo)
        pdf.drawRightString(x_dir, self.y, valor)
        self.y -= 20 if destaque else 16

    def _desenhar_resumo_financeiro(self):
        pedido      = self.pedido
        combo_desc  = float(getattr(pedido, 'combo_desconto', 0.0) or 0.0)
        subtotal    = pedido.subtotal_itens
        desc_cliente= subtotal * 0.10 if getattr(pedido, 'teve_desconto', False) else 0.0

        if self.y < 160:
            self._nova_pagina_continuacao()

        self._linha_resumo("Subtotal dos itens", f"R$ {subtotal:.2f}")
        if desc_cliente > 0:
            self._linha_resumo("Desconto (cliente cadastrado)",
                               f"- R$ {desc_cliente:.2f}")
        if combo_desc > 0:
            self._linha_resumo("Desconto combo", f"- R$ {combo_desc:.2f}")
        if pedido.taxa_entrega > 0:
            self._linha_resumo("Taxa de entrega",
                               f"R$ {pedido.taxa_entrega:.2f}")

        x_dir = self.pagina_largura - self.margem
        self.pdf.setStrokeColor(self.COR_LINHA)
        self.pdf.line(x_dir - 220, self.y + 6, x_dir, self.y + 6)
        self.y -= 10
        self._linha_resumo("TOTAL A PAGAR",
                           f"R$ {pedido.preco_final:.2f}", destaque=True)

    # ── Rodapé ────────────────────────────────────────────────────────
    def _desenhar_rodape(self):
        pdf     = self.pdf
        largura = self.pagina_largura
        pdf.setStrokeColor(self.COR_LINHA)
        pdf.line(self.margem, 50, largura - self.margem, 50)
        pdf.setFont("Helvetica-Oblique", 9)
        pdf.setFillColor(self.COR_TEXTO_SUAVE)
        pdf.drawCentredString(largura / 2, 36,
            "Obrigado pela preferência! Volte sempre — GB Pizzaria")
        pdf.setFont("Helvetica", 7.5)
        pdf.drawCentredString(largura / 2, 24,
            "Este documento não possui valor fiscal.")


# ── Relatório de caixa ────────────────────────────────────────────────
class RelatorioCaixaPDF:
    COR_PRIMARIA        = ComprovantePDF.COR_PRIMARIA
    COR_PRIMARIA_ESCURA = ComprovantePDF.COR_PRIMARIA_ESCURA
    COR_TEXTO           = ComprovantePDF.COR_TEXTO
    COR_TEXTO_SUAVE     = ComprovantePDF.COR_TEXTO_SUAVE
    COR_LINHA           = ComprovantePDF.COR_LINHA
    COR_FAIXA           = ComprovantePDF.COR_FAIXA
    ALTURA_LINHA        = 22   # mesmo padrão

    def __init__(self, fechamento):
        self.fechamento = fechamento
        self.pagina_largura, self.pagina_altura = A4
        self.margem = 18 * mm
        self.y = 0
        self.pdf = None

    def gerar(self):
        buffer = BytesIO()
        self.pdf = canvas.Canvas(buffer, pagesize=A4)
        self._cabecalho()
        self._resumo_geral()
        self._formas_pagamento()
        self._rodape()
        self.pdf.save()
        buffer.seek(0)
        return buffer

    def _cabecalho(self):
        pdf = self.pdf
        largura, altura = self.pagina_largura, self.pagina_altura

        pdf.setFillColor(self.COR_PRIMARIA)
        pdf.rect(0, altura - 95, largura, 95, fill=1, stroke=0)

        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 22)
        pdf.drawString(self.margem, altura - 48, "GB PIZZARIA")
        pdf.setFont("Helvetica", 11)
        pdf.drawString(self.margem, altura - 66, "Relatório de Fechamento de Caixa")

        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawRightString(largura - self.margem, altura - 48,
                            f"CAIXA #{self.fechamento.id}")
        pdf.setFont("Helvetica", 9)
        pdf.drawRightString(largura - self.margem, altura - 66,
                            self.fechamento.data_fechamento)
        self.y = altura - 120

    def _resumo_geral(self):
        pdf = self.pdf
        largura = self.pagina_largura

        pdf.setFillColor(self.COR_FAIXA)
        pdf.roundRect(self.margem, self.y - 60,
                      largura - 2 * self.margem, 80, 6, fill=1, stroke=0)

        col1, col2 = self.margem + 14, largura / 2 + 10
        y_topo = self.y + 4

        def campo(x, y, rotulo, valor):
            pdf.setFont("Helvetica-Bold", 8.5)
            pdf.setFillColor(self.COR_TEXTO_SUAVE)
            pdf.drawString(x, y, rotulo.upper())
            pdf.setFont("Helvetica-Bold", 12)
            pdf.setFillColor(self.COR_TEXTO)
            pdf.drawString(x, y - 16, valor)

        campo(col1, y_topo,       "Operador",         self.fechamento.usuario)
        campo(col2, y_topo,       "Pedidos no turno", str(self.fechamento.total_vendas))
        campo(col1, y_topo - 36,  "Faturamento total",
              f"R$ {self.fechamento.faturamento_total:.2f}")
        self.y -= 70

    def _formas_pagamento(self):
        pdf   = self.pdf
        AL    = self.ALTURA_LINHA
        largura = self.pagina_largura
        x_esq, x_dir = self.margem, largura - self.margem

        self.y -= 16
        pdf.setFont("Helvetica-Bold", 12)
        pdf.setFillColor(self.COR_PRIMARIA_ESCURA)
        pdf.drawString(x_esq, self.y, "DIVISÃO POR FORMA DE PAGAMENTO")
        self.y -= 18

        ALTURA_HEADER = 20
        pdf.setFillColor(self.COR_PRIMARIA)
        pdf.rect(x_esq, self.y - ALTURA_HEADER, x_dir - x_esq, ALTURA_HEADER,
                 fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 9)
        y_ht = self.y - ALTURA_HEADER + 7
        pdf.drawString(x_esq + 8,  y_ht, "FORMA DE PAGAMENTO")
        pdf.drawRightString(x_dir - 8, y_ht, "VALOR")
        self.y -= ALTURA_HEADER + 16

        for forma, valor in self.fechamento.resumo_pagamentos.items():
            pdf.setFillColor(self.COR_TEXTO)
            pdf.setFont("Helvetica", 10.5)
            pdf.drawString(x_esq + 8, self.y, forma)
            pdf.setFont("Helvetica-Bold", 10.5)
            pdf.drawRightString(x_dir - 8, self.y, f"R$ {valor:.2f}")
            self.y -= AL

        pdf.setStrokeColor(self.COR_LINHA)
        pdf.line(x_esq, self.y + 6, x_dir, self.y + 6)
        self.y -= 24

        pdf.setFont("Helvetica-Bold", 13)
        pdf.setFillColor(self.COR_PRIMARIA_ESCURA)
        pdf.drawString(x_esq, self.y, "TOTAL GERAL")
        pdf.drawRightString(x_dir, self.y,
                            f"R$ {self.fechamento.faturamento_total:.2f}")

    def _rodape(self):
        pdf = self.pdf
        largura = self.pagina_largura
        pdf.setStrokeColor(self.COR_LINHA)
        pdf.line(self.margem, 50, largura - self.margem, 50)
        pdf.setFont("Helvetica-Oblique", 9)
        pdf.setFillColor(self.COR_TEXTO_SUAVE)
        pdf.drawCentredString(largura / 2, 36,
            "GB Pizzaria — Relatório interno de fechamento de caixa")
        pdf.setFont("Helvetica", 7.5)
        pdf.drawCentredString(largura / 2, 24,
            "Este documento não possui valor fiscal.")