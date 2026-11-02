import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Dashboard de Performance de Ações (B3)",
    page_icon="📈",
    layout="wide"
)

# Título principal da aplicação
st.title("📊 Análise de Performance de Mercado de Ações & Séries Temporais (B3)")
st.markdown("Painel executivo desenvolvido para análise de ativos da B3 no período de 2021 a 2023.")

# 1. LISTA OFICIAL DE ATIVOS (Linha 2)
TICKERS_B3 = [
    "WEGE3.SA", "EMBR3.SA", "VALE3.SA", "GGBR4.SA", 
    "KLBN11.SA", "PETR4.SA", "PRIO3.SA", "EGIE3.SA", 
    "ITUB4.SA", "BBDC4.SA", "ABEV3.SA", "RENT3.SA"
]

# 2. FUNÇÃO DE ETL SEGURA COM LOOP E CACHE (@st.cache_data)
@st.cache_data(ttl=86400)
def carregar_dados(tickers, inicio="2021-01-01", fim="2023-12-31"):
    dfs = []
    for t in tickers:
        try:
            df_t = yf.download(t, start=inicio, end=fim, progress=False)
            if not df_t.empty:
                # Pega Ajustado ou Fechamento normal como contingência
                if "Adj Close" in df_t.columns:
                    s = df_t["Adj Close"]
                elif "Close" in df_t.columns:
                    s = df_t["Close"]
                else:
                    continue
                
                if isinstance(s, pd.DataFrame):
                    s = s.iloc[:, 0]
                dfs.append(s.rename(t))
        except Exception:
            continue
            
    if dfs:
        df = pd.concat(dfs, axis=1)
    else:
        df = pd.DataFrame()
        
    df = df.ffill().bfill()
    return df

# Carregamento dos dados
with st.spinner("Carregando dados históricos da B3 via yfinance..."):
    df_precos = carregar_dados(TICKERS_B3)

# 3. BARRA LATERAL (SIDEBAR) - FILTROS DINÂMICOS
st.sidebar.header("⚙️ Painel de Controle")

opcoes_disponiveis = list(df_precos.columns)
defaults_iniciais = [t for t in ["WEGE3.SA", "PETR4.SA", "VALE3.SA", "ITUB4.SA"] if t in opcoes_disponiveis]
if not defaults_iniciais and opcoes_disponiveis:
    defaults_iniciais = opcoes_disponiveis[:4]

ativos_selecionados = st.sidebar.multiselect(
    "Selecione os Ativos para Comparação:",
    options=opcoes_disponiveis,
    default=defaults_iniciais
)

data_inicio = st.sidebar.date_input("Data Inicial", value=pd.to_datetime("2021-01-01"))
data_fim = st.sidebar.date_input("Data Final", value=pd.to_datetime("2023-12-31"))

# Botão de Reset de Filtros
if st.sidebar.button("Resetar Filtros"):
    st.rerun()

# Validação e Filtragem de Dados
if not ativos_selecionados:
    st.warning("⚠️ Por favor, selecione pelo menos um ativo na barra lateral para exibir a análise.")
    st.stop()

df_filtrado = df_precos.loc[str(data_inicio):str(data_fim), ativos_selecionados]
if isinstance(df_filtrado, pd.Series):
    df_filtrado = df_filtrado.to_frame(name=ativos_selecionados)

# ==================================
# 4. ESTRUTURAÇÃO EM ABAS (st.tabs)
# ==================================
aba1, aba2, aba3, aba4 = st.tabs([
    "📈 Performance (Base 100)", 
    "⚖️ Risco vs Retorno", 
    "📉 Drawdowns & Volatilidade", 
    "📊 Estatísticas & Médias Móveis"
])

with aba1:
    st.subheader("Evolução Comparativa Normalizada (Base 100)")
    st.markdown("Mede o crescimento acumulado de um capital investido no início do período.")
    
    df_base100 = (df_filtrado / df_filtrado.iloc[0]) * 100
    
    fig_base100 = px.line(
        df_base100, 
        labels={"value": "Valor Normalizado (Base 100)", "Date": "Data", "variable": "Ativo"},
        template="plotly_white"
    )
    fig_base100.add_hline(y=100, line_dash="dash", line_color="gray", annotation_text="Ponto de Partida (100)")
    st.plotly_chart(fig_base100, use_container_width=True)

with aba2:
    st.subheader("Relação Risco x Retorno")
    retorno_acumulado = ((df_filtrado.iloc[-1] / df_filtrado.iloc[0]) - 1) * 100
    volatilidade_anual = df_filtrado.pct_change().std() * np.sqrt(252) * 100
    
    df_risco_retorno = pd.DataFrame({
        "Retorno Acumulado (%)": retorno_acumulado,
        "Volatilidade Anualizada (% a.a.)": volatilidade_anual
    }).reset_index()
    df_risco_retorno.columns = ["Ativo", "Retorno Acumulado (%)", "Volatilidade Anualizada (% a.a.)"]
    
    fig_scatter = px.scatter(
        df_risco_retorno,
        x="Volatilidade Anualizada (% a.a.)",
        y="Retorno Acumulado (%)",
        text="Ativo",
        size_max=60,
        template="plotly_white",
        title="Dispersão: Volatilidade vs Retorno"
    )
    fig_scatter.update_traces(textposition='top center')
    st.plotly_chart(fig_scatter, use_container_width=True)

with aba3:
    st.subheader("Análise de Drawdown (Queda a partir do Topo)")
    rolling_max = df_filtrado.cummax()
    drawdown = (df_filtrado - rolling_max) / rolling_max * 100
    
    fig_dd = px.line(
        drawdown,
        labels={"value": "Drawdown (%)", "Date": "Data", "variable": "Ativo"},
        template="plotly_white",
        title="Curva de Drawdown Histórico"
    )
    st.plotly_chart(fig_dd, use_container_width=True)

with aba4:
    st.subheader("Médias Móveis e Tendência")
    ativo_escolhido = st.selectbox("Escolha o ativo para inspeção de Médias Móveis:", ativos_selecionados)
    
    df_ma = pd.DataFrame(index=df_filtrado.index)
    df_ma["Fechamento"] = df_filtrado[ativo_escolhido]
    df_ma["SMA 21"] = df_filtrado[ativo_escolhido].rolling(window=21).mean()
    df_ma["SMA 50"] = df_filtrado[ativo_escolhido].rolling(window=50).mean()
    
    fig_ma = px.line(
        df_ma,
        template="plotly_white",
        title=f"Preço e Médias Móveis (SMA 21 e SMA 50) - {ativo_escolhido}"
    )
    st.plotly_chart(fig_ma, use_container_width=True)

# ==========================================
# 5. KPIS ESTRATÉGICOS (st.metric) COM CAIXAS/CONTAINERS
# ==========================================
st.markdown("---")
st.subheader("📌 Indicadores Chave de Desempenho (KPIs da Carteira)")

retorno_acumulado_clean = retorno_acumulado.dropna()
volatilidade_anual_clean = volatilidade_anual.dropna()

if not retorno_acumulado_clean.empty:
    # Criamos 4 colunas para os KPIs
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

    retorno_medio_carteira = retorno_acumulado_clean.mean()
    melhor_ativo = str(retorno_acumulado_clean.idxmax()).replace(".SA", "")
    pior_ativo = str(retorno_acumulado_clean.idxmin()).replace(".SA", "")
    vol_media_carteira = volatilidade_anual_clean.mean() if not volatilidade_anual_clean.empty else 0

    # Cada métrica inserida em um container com borda (efeito de caixa/card)
    with kpi_col1:
        with st.container(border=True):
            st.metric("Retorno Médio da Carteira", f"{retorno_medio_carteira:.2f}%", delta="Acumulado")

    with kpi_col2:
        with st.container(border=True):
            st.metric("Ativo Destaque (Alta)", melhor_ativo, delta=f"{retorno_acumulado_clean.max():.2f}%")

    with kpi_col3:
        with st.container(border=True):
            st.metric("Ativo Menor Performance", pior_ativo, delta=f"{retorno_acumulado_clean.min():.2f}%", delta_color="inverse")

    with kpi_col4:
        with st.container(border=True):
            st.metric("Volatilidade Média", f"{vol_media_carteira:.2f}% a.a.")
else:
    st.warning("⚠️ Dados insuficientes para calcular os KPIs no período selecionado.")