import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Monitor Fênix",
    page_icon="☀️",
    layout="wide"
)

st.markdown("""
<style>
    .stApp { background-color: #0f1117; }
    .kpi-card {
        background: #1c1f2e;
        border: 1px solid #2e3250;
        border-radius: 10px;
        padding: 20px 24px;
        text-align: center;
    }
    .kpi-label {
        color: #8b93b0;
        font-size: 0.78rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        margin-bottom: 8px;
    }
    .kpi-value {
        color: #ffffff;
        font-size: 2rem;
        font-weight: 700;
        line-height: 1;
    }
    .kpi-value.alert { color: #f97316; }
    .kpi-value.good  { color: #22c55e; }
    .section-title {
        color: #e2e8f0;
        font-size: 1rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        border-left: 3px solid #3b82f6;
        padding-left: 10px;
        margin-bottom: 16px;
    }
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)


# SIDEBAR COM PARÂMETROS DA SIMULAÇÃO

with st.sidebar:
    st.markdown("## Monitor Solar")
    st.markdown("---")

    st.markdown("### Configuração da Usina")

    capacidade_kwp = st.slider(
        "Capacidade instalada (kWp)",
        min_value=50, max_value=1000,
        value=250, step=50,
        help="Potência máxima de pico da usina em kilowatts-pico"
    )

    dias = st.slider(
        "Período de análise (dias)",
        min_value=1, max_value=30,
        value=7
    )

    pr_threshold = st.slider(
        "Threshold de alerta — PR (%)",
        min_value=50, max_value=90,
        value=75,
        help="Horas com PR abaixo desse valor geram alertas"
    )

    st.markdown("---")
    st.markdown("### Condições climáticas")

    # Fator de degradação simula dias nublados/chuvosos
    fator_clima = st.select_slider(
        "Qualidade do período",
        options=["Chuvoso", "Nublado", "Parcialmente nublado", "Ensolarado"],
        value="Parcialmente nublado"
    )

    # Mapeia a escolha para um multiplicador numérico
    clima_map = {
        "Chuvoso": 0.45,
        "Nublado": 0.65,
        "Parcialmente nublado": 0.80,
        "Ensolarado": 0.95
    }
    fator = clima_map[fator_clima]

    st.markdown("---")
    st.caption("Projeto demonstrativo — dados simulados")


# GERAÇÃO DE DADOS SIMULADOS

@st.cache_data  # Cache: só recalcula se os parâmetros mudarem
def gerar_dados(capacidade, dias, fator_clima_val, seed=42):
    np.random.seed(seed)

    # Cria um timestamp por hora durante o período escolhido
    inicio = datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=dias)
    horas = pd.date_range(start=inicio, periods=dias * 24, freq="h")

    # Hora do dia (0–23) para cada timestamp
    hora_do_dia = horas.hour.values  # array numpy

    # ── Curva de irradiância esperada 
    # Seno entre 6h e 19h → simula nascer/pôr do sol.
    # Fora desse intervalo a irradiância é zero (noite).
    irrad_esperada = np.where(
        (hora_do_dia >= 6) & (hora_do_dia <= 19),
        np.sin(np.pi * (hora_do_dia - 6) / 13) * 1000,  # W/m² no pico
        0.0
    )

    # ── Geração esperada 
    # Fórmula: Capacidade (kWp) × Irradiância (kW/m²) × eficiência padrão (18%)
    geracao_esperada = capacidade * (irrad_esperada / 1000) * 0.18

    # ── Geração real 
    # Aplicamos o fator climático + ruído aleatório (±15%)
    ruido = np.random.uniform(0.85, 1.15, size=len(horas))
    geracao_real = geracao_esperada * fator_clima_val * ruido

    # Não pode gerar energia negativa
    geracao_real = np.clip(geracao_real, 0, None)

    # ── Performance Ratio 
    # Evitamos divisão por zero nas horas de noite (esperada = 0)
    pr = np.where(
        geracao_esperada > 0,
        (geracao_real / geracao_esperada) * 100,
        np.nan  # NaN para horas sem sol
    )

    df = pd.DataFrame({
        "timestamp": horas,
        "hora": hora_do_dia,
        "geracao_real_kwh":     geracao_real.round(2),
        "geracao_esperada_kwh": geracao_esperada.round(2),
        "irradiancia_wm2":      irrad_esperada.round(1),
        "performance_ratio":    pr.round(1),
    })

    return df


df = gerar_dados(capacidade_kwp, dias, fator)

# Filtra apenas horas com sol para os cálculos de PR
df_sol = df[df["geracao_esperada_kwh"] > 0].copy()

# CABEÇALHO

st.markdown("## Dashboard de Monitoramento Solar")
st.markdown(
    f"**Usina simulada** · {capacidade_kwp} kWp · "
    f"Últimos **{dias} dias** · Clima: **{fator_clima}**"
)
st.markdown("---")

# KPIs — CARTÕES DE MÉTRICAS PRINCIPAIS

geracao_total   = df["geracao_real_kwh"].sum()
pr_medio        = df_sol["performance_ratio"].mean()
horas_alerta    = (df_sol["performance_ratio"] < pr_threshold).sum()
horas_operando  = len(df_sol)
disponibilidade = ((horas_operando - horas_alerta) / horas_operando * 100)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Geração Total</div>
        <div class="kpi-value">{geracao_total:,.0f}</div>
        <div class="kpi-label">kWh</div>
    </div>""", unsafe_allow_html=True)

with col2:
    cor_pr = "good" if pr_medio >= pr_threshold else "alert"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">PR Médio</div>
        <div class="kpi-value {cor_pr}">{pr_medio:.1f}%</div>
        <div class="kpi-label">Performance Ratio</div>
    </div>""", unsafe_allow_html=True)

with col3:
    cor_alerta = "alert" if horas_alerta > 0 else "good"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Horas em Alerta</div>
        <div class="kpi-value {cor_alerta}">{horas_alerta}</div>
        <div class="kpi-label">PR abaixo de {pr_threshold}%</div>
    </div>""", unsafe_allow_html=True)

with col4:
    cor_disp = "good" if disponibilidade >= 90 else "alert"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">✅ Disponibilidade</div>
        <div class="kpi-value {cor_disp}">{disponibilidade:.1f}%</div>
        <div class="kpi-label">horas sem alerta</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# GRÁFICO 1 — GERAÇÃO REAL vs ESPERADA

st.markdown('<div class="section-title">Geração Real vs. Esperada</div>', unsafe_allow_html=True)

fig1 = go.Figure()

# Área da geração esperada (referência)
fig1.add_trace(go.Scatter(
    x=df["timestamp"],
    y=df["geracao_esperada_kwh"],
    name="Esperada",
    fill="tozeroy",
    fillcolor="rgba(59,130,246,0.15)",
    line=dict(color="#3b82f6", width=1.5, dash="dot"),
    hovertemplate="<b>Esperada:</b> %{y:.2f} kWh<extra></extra>"
))

# Linha da geração real
fig1.add_trace(go.Scatter(
    x=df["timestamp"],
    y=df["geracao_real_kwh"],
    name="Real",
    fill="tozeroy",
    fillcolor="rgba(34,197,94,0.20)",
    line=dict(color="#22c55e", width=2),
    hovertemplate="<b>Real:</b> %{y:.2f} kWh<extra></extra>"
))

fig1.update_layout(
    height=320,
    paper_bgcolor="#0f1117",
    plot_bgcolor="#0f1117",
    font=dict(color="#8b93b0", size=12),
    legend=dict(orientation="h", y=1.08, bgcolor="rgba(0,0,0,0)"),
    xaxis=dict(gridcolor="#1c2035", showline=False),
    yaxis=dict(gridcolor="#1c2035", showline=False, title="kWh"),
    hovermode="x unified",
    margin=dict(l=0, r=0, t=10, b=0)
)

st.plotly_chart(fig1, use_container_width=True)

# GRÁFICO 2 — PERFORMANCE RATIO POR HORA

st.markdown('<div class="section-title">Performance Ratio por Hora</div>', unsafe_allow_html=True)

df_pr = df_sol.copy()
cores = df_pr["performance_ratio"].apply(
    lambda x: "#22c55e" if x >= pr_threshold else "#f97316"
)

fig2 = go.Figure()

fig2.add_trace(go.Bar(
    x=df_pr["timestamp"],
    y=df_pr["performance_ratio"],
    marker_color=cores,
    name="PR",
    hovertemplate="<b>PR:</b> %{y:.1f}%<extra></extra>"
))

# Linha do threshold
fig2.add_hline(
    y=pr_threshold,
    line_dash="dash",
    line_color="#f97316",
    annotation_text=f"Threshold: {pr_threshold}%",
    annotation_font_color="#f97316"
)

fig2.update_layout(
    height=280,
    paper_bgcolor="#0f1117",
    plot_bgcolor="#0f1117",
    font=dict(color="#8b93b0", size=12),
    xaxis=dict(gridcolor="#1c2035"),
    yaxis=dict(gridcolor="#1c2035", range=[0, 110], title="PR (%)"),
    margin=dict(l=0, r=0, t=10, b=0),
    showlegend=False
)

st.plotly_chart(fig2, use_container_width=True)

# TABELA DE ALERTAS

alertas = df_sol[df_sol["performance_ratio"] < pr_threshold][[
    "timestamp", "geracao_real_kwh", "geracao_esperada_kwh", "performance_ratio"
]].copy()

alertas.columns = ["Timestamp", "Geração Real (kWh)", "Geração Esperada (kWh)", "PR (%)"]
alertas["Timestamp"] = alertas["Timestamp"].dt.strftime("%d/%m %H:%M")

if not alertas.empty:
    st.markdown(
        f'<div class="section-title">Alertas — {len(alertas)} ocorrência(s)</div>',
        unsafe_allow_html=True
    )
    st.dataframe(
        alertas.reset_index(drop=True),
        use_container_width=True,
        height=min(300, 38 + len(alertas) * 35)
    )
else:
    st.success("✅ Nenhum alerta no período. Performance dentro do esperado!")
