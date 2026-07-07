import pandas as pd
import matplotlib.pyplot as plt

# Ler os resultados
df = pd.read_csv('resultados.csv')

# 1. FIX: Filtrar um n_holders específico para não misturar os cenários
df_plot = df[df['n_holders'] == 1000].copy()

# ==============================================================================
# Gráfico 1: Custo de Takeover vs Orçamento de Suborno
# ==============================================================================
plt.figure(figsize=(10, 6))

df_takeover = df_plot[df_plot['metrica'].isin(['custo_takeover', 'custo_takeover_51'])]

# Plotando com matplotlib puro para aplicar a coluna ic95 perfeitamente
for metrica in ['custo_takeover', 'custo_takeover_51']:
    for dist in df_takeover['distribuicao'].unique():
        # Filtra a sub-tabela e garante a ordem do eixo X
        df_sub = df_takeover[(df_takeover['metrica'] == metrica) & (df_takeover['distribuicao'] == dist)]
        df_sub = df_sub.sort_values('orcamento_suborno')
        
        # Ajuste de legenda e visual
        label = f"{'Takeover 1/3' if metrica == 'custo_takeover' else 'Takeover 51%'} ({dist})"
        estilo_linha = '-' if metrica == 'custo_takeover' else '--'
        
        # 3. FIX: Adição do argumento yerr referenciando a coluna 'ic95'
        plt.errorbar(
            df_sub['orcamento_suborno'], 
            df_sub['media'], 
            yerr=df_sub['ic95'], 
            label=label, 
            marker='o', 
            capsize=4, 
            linestyle=estilo_linha
        )

plt.title('Impacto do Suborno no Custo de Takeover (n_holders = 1000)')
plt.ylabel('Custo de Takeover (Fração do Stake)')
plt.xlabel('Orçamento Injetado pelo Invasor')
plt.grid(True, linestyle='--', alpha=0.7)
plt.legend()
plt.tight_layout()
plt.savefig('grafico_takeover.png')
plt.close()

# ==============================================================================
# Gráfico 2: Custo de Takeover vs Orçamento de Suborno (Com Subplots / Zoom)
# ==============================================================================
# Criar uma figura mais larga contendo 2 gráficos (1 linha, 2 colunas)
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

df_takeover = df_plot[df_plot['metrica'].isin(['custo_takeover', 'custo_takeover_51'])]

for metrica in ['custo_takeover', 'custo_takeover_51']:
    # Direciona o Takeover 1/3 para o gráfico da esquerda (ax1) e o 51% para a direita (ax2)
    ax = ax1 if metrica == 'custo_takeover' else ax2
    titulo_subplot = 'Takeover 1/3 (Poder de Veto)' if metrica == 'custo_takeover' else 'Takeover 51% (Maioria Absoluta)'
    
    for dist in df_takeover['distribuicao'].unique():
        df_sub = df_takeover[(df_takeover['metrica'] == metrica) & (df_takeover['distribuicao'] == dist)]
        df_sub = df_sub.sort_values('orcamento_suborno')
        
        ax.errorbar(
            df_sub['orcamento_suborno'], 
            df_sub['media'], 
            yerr=df_sub['ic95'], 
            label=f"Distribuição: {dist}", 
            marker='o', 
            capsize=4, 
            linestyle='-'
        )
        
    ax.set_title(titulo_subplot)
    ax.set_ylabel('Custo de Takeover (Fração do Stake)')
    ax.set_xlabel('Orçamento Injetado pelo Invasor')
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend()

# Título principal abrangendo os dois gráficos
plt.suptitle('Impacto do Suborno no Custo de Takeover (n_holders = 1000)', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig('grafico_takeover_zoom.png')
plt.close()

# ==============================================================================
# Gráfico 3: O "Gap" de Concentração (Gini) nas Três Camadas
# ==============================================================================
df_gini = df_plot[(df_plot['metrica'] == 'gini') & (df_plot['orcamento_suborno'] == 0.0)]

# Pivotando para usar a plotagem de barras do Pandas (que lida fácil com colunas de erro)
df_pivot = df_gini.pivot(index='distribuicao', columns='camada', values='media')
df_err = df_gini.pivot(index='distribuicao', columns='camada', values='ic95')

# Garantindo a ordem lógica das camadas nas barras
camadas_ordem = ['stake', 'eleito', 'produzido']
df_pivot = df_pivot[camadas_ordem]
df_err = df_err[camadas_ordem]

plt.figure(figsize=(10, 6))
# A plotagem do Pandas aceita o dataframe de erros diretamente no yerr
df_pivot.plot(kind='bar', yerr=df_err, capsize=4, ax=plt.gca(), edgecolor='black')

plt.title('Salto de Concentração (Gini) entre as Camadas (n_holders = 1000)')
plt.ylabel('Coeficiente de Gini (Mais perto de 1 = Mais concentrado)')
plt.xlabel('Distribuição Inicial de Riqueza')
plt.xticks(rotation=0)
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.tight_layout()
plt.savefig('grafico_gini_camadas.png')
plt.close()




print("Gráficos gerados com sucesso! Verifique os ficheiros PNG na pasta.")