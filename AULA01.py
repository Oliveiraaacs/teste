import PyPDF2
import re
import math
from pathlib import Path
from tkinter import Tk, filedialog
import pdfplumber

def extrair_razao_social(arquivo_pdf):
    """
    Extrai a Razão Social de um arquivo PDF, procurando pela linha que contém
    "R. Social" dentro da seção "DADOS PARA FATURAMENTO" e ignorando a Razão Social
    do fornecedor.
    """
    caminho = Path(arquivo_pdf)

    if not caminho.exists():
        return f"❌ Erro: Arquivo não encontrado em {caminho}"

    try:
        with open(caminho, "rb") as pdf_file:
            leitor = PyPDF2.PdfReader(pdf_file)
            
            razao_social_a_ignorar = "MMFOODS IND E COM DE ALIM LTDA"
            
            for pagina in leitor.pages:
                texto_pagina = pagina.extract_text()

                if texto_pagina:
                    # Encontra o texto da seção "DADOS PARA FATURAMENTO"
                    secao_faturamento_match = re.search(r"DADOS PARA FATURAMENTO", texto_pagina, re.IGNORECASE)

                    if secao_faturamento_match:
                        # Extrai o texto a partir do ponto onde a seção de faturamento começa
                        texto_apos_faturamento = texto_pagina[secao_faturamento_match.end():]
                        
                        # Captura a razão social que você precisa e limpa a linha de lixo
                        padrao_sendas = re.compile(r"R\. Social\s+(.*?SENDAS.*?)(?=\s*R\. Social|\s*Endereço|\s*Bairro|\s*Cidade|\s*Cep|\n|$)", re.IGNORECASE | re.DOTALL)
                        resultado = padrao_sendas.search(texto_apos_faturamento)

                        if resultado:
                            razao_social = resultado.group(1).strip()
                            
                            # Limpa a string removendo a razão social do fornecedor
                            razao_social = re.sub(razao_social_a_ignorar, '', razao_social, flags=re.IGNORECASE).strip()

                            # Verifica se o resultado final não está vazio
                            if razao_social:
                                return razao_social
    
    except Exception as e:
        return f"❌ Erro ao processar o arquivo PDF: {e}"

    # Se o loop terminar sem encontrar a informação, retorna a mensagem de aviso.
    return "⚠️ Razão Social não encontrada na seção 'Dados para Faturamento'."

def extrair_quantidades_produtos(arquivo_pdf, mapeamento_produtos, conversao_pesos):
    """
    Lê o PDF e extrai quantidades por código, olhando uma janela ANTES do código
    para capturar o token de quantidade no formato '00018,00KG' ou '0004,00UN', etc.
    Depois, converte usando 'conversao_pesos' e aplica floor.
    """
    caminho = Path(arquivo_pdf)
    if not caminho.exists():
        return f"❌ Erro: Arquivo não encontrado em {caminho}"

    try:
        # 1) Extrair texto com pdfplumber (mais confiável para este layout)
        texto = ""
        with pdfplumber.open(caminho) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                if t:
                    texto += t + "\n"

        if not texto.strip():
            return "⚠️ Não foi possível extrair texto do PDF."

        # 2) Para cada código do mapeamento, procure no texto e analise o contexto anterior
        quantidades = {}
        # Quantidade: números com possível zero à esquerda e vírgula decimal (ex.: 0018,00 / 004,00)
        # Unidade: KG ou UN (às vezes vem sem espaço, ex.: '0018,00KG')
        padrao_qtd_un = re.compile(
            r"(\d{1,4}(?:\.\d{3})*,\d{2})\s*(KG|UN)\b",
            re.IGNORECASE
        )

        for codigo, sigla in mapeamento_produtos.items():
            # encontre TODAS as ocorrências do código
            ocorrencias = [m for m in re.finditer(re.escape(codigo), texto)]
            if not ocorrencias:
                # não achou o código — segue para o próximo
                continue

            # Para cada ocorrência do código, examinamos um trecho ANTES do código
            # A janela pode ser ajustada conforme o PDF; 200 costuma bastar.
            janela = 220
            melhor_qtd = None  # guardaremos a última qtd na janela (a mais próxima do código)
            melhor_un = None

            for m in ocorrencias:
                ini_contexto = max(0, m.start() - janela)
                fim_contexto = m.start()
                contexto = texto[ini_contexto:fim_contexto]

                # pegue TODAS as quantidades na janela e escolha a ÚLTIMA (mais próxima do código)
                matches = list(padrao_qtd_un.finditer(contexto))
                if matches:
                    qtd_match = matches[-1]  # a última no contexto
                    melhor_qtd = qtd_match.group(1)
                    melhor_un = qtd_match.group(2).upper()

            if melhor_qtd:
                # normaliza número: '0018,00' -> 18.00
                qtd_num = float(melhor_qtd.replace('.', '').replace(',', '.'))

                # 3) Converte para "unidades finais" pelo peso do produto (se houver)
                peso_produto = conversao_pesos.get(sigla, 1.0)

                # Se unidade é UN, normalmente não precisa dividir por peso (mas mantemos lógica caso tenha peso)
                if peso_produto and peso_produto > 0:
                    if melhor_un == "KG":
                        qtd_final = math.floor(qtd_num / peso_produto)
                    else:
                        # melhor_un == "UN": quantidade já está em unidades
                        qtd_final = math.floor(qtd_num / 1.0)
                else:
                    # fallback seguro
                    qtd_final = math.floor(qtd_num)

                quantidades[sigla] = int(qtd_final)

        return quantidades

    except Exception as e:
        return f"❌ Erro ao processar o arquivo PDF: {e}"


if __name__ == "__main__":
    # Esconde a janela principal do Tkinter para não aparecer na tela
    Tk().withdraw()

    # Mapeamento dos produtos fornecido pelo usuário
    mapeamento_produtos = {
        '1179486': 'A',
        '1178051': 'IA',
        '1179573': 'MA',
        '1179490': 'BAG',
        '1179579': 'MBA',
        '1179491': 'FILÃO',
        '1179505': 'ITA',
        '1179527': 'RUSTICA',
        '1179515': 'S. ITA',
        '1179542': 'BC',
        '1179538': 'BF',
        '1179541': 'BPQ',
        '1179513': 'MILHO',
        '1179512': 'COCO',
        '1179535': 'BATA',
        '1179514': 'HAM',
        '1179516': 'DOG',
        '1178049': 'PANE.',
        '1179494': 'CHOCO',
        '1179504': 'VOVO',
        '1179510': 'BROA',
        '1179506': 'BISNA',
        '1179508': 'LEITE',
        '1179519': 'SONHO',
        '1179524': 'M SON',
        '1179523': 'L.MEL',
        '1179501': 'CREME',
        '1179540': 'CHIPA',
        '1179558': 'PQ 15',
        '1179583': 'BL CHO',
        '1179577': 'BL LARA',
        '1179580': 'BL FUB',
        '1179582': 'BL COCO',
        '1179581': 'BL BAU'
    }

    # Novo dicionário com as conversões de peso fornecidas
    conversao_pesos = {
        'A': 5.0,
        'IA': 5.0,
        'MA': 5.0,
        'BAG': 5.0,
        'MBA': 5.0,
        'FILÃO': 5.0,
        'ITA': 5.0,
        'RUSTICA': 5.0,
        'S. ITA': 5.0,
        'BC': 3.0,
        'BF': 3.0,
        'BPQ': 3.0,
        'MILHO': 5.0,
        'COCO': 5.0,
        'BATA': 5.0,
        'HAM': 5.0,
        'DOG': 5.0,
        'PANE.': 3.5,
        'CHOCO': 3.5,
        'VOVO': 5.0,
        'BROA': 5.0,
        'BISNA': 5.0,
        'LEITE': 5.0,
        'SONHO': 1.0,
        'M SON': 2.5,
        'L.MEL': 2.5,
        'CREME': 9.0,
        'CHIPA': 2.0,
        'PQ 15': 2.0,
        'BL CHO': 1.8,
        'BL LARA': 1.8,
        'BL FUB': 1.8,
        'BL COCO': 1.8,
        'BL BAU': 1.8
    }

    # Abre a janela para o usuário escolher o arquivo PDF
    arquivo = filedialog.askopenfilename(
        title="Selecione o arquivo PDF",
        filetypes=[("Arquivos PDF", "*.pdf")]
    )

    if arquivo:
        razao_social = extrair_razao_social(arquivo)
        quantidades = extrair_quantidades_produtos(arquivo, mapeamento_produtos, conversao_pesos)

        print("Razão Social:", razao_social)
        print("\nQuantidades de Produtos:")
        for produto, quantidade in quantidades.items():
            print(f"- {produto}: {quantidade}")
    else:
        print("⚠️ Nenhum arquivo selecionado.")
