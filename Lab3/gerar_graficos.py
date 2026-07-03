import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Ler os resultados
df = pd.read_csv('resultados.csv')

# 1. Gráfico: Custo de Takeover vs Orçamento de Suborno
plt.figure(figsize=(10, 6))
sns.lineplot(data=df[df['metrica'] == 'custo_takeover'], 
             x='orcamento_suborno', y='media', hue='distribuicao', marker='o', errorbar=None)
plt.title('Impacto do Suborno no Custo de Takeover (Mais de 1/3 da rede)')
plt.ylabel('Custo de Takeover (Fração do Stake)')
plt.xlabel('Orçamento Injetado pelo Invasor')
plt.grid(True, linestyle='--', alpha=0.7)
plt.savefig('grafico_takeover.png')
plt.close()

# 2. Gráfico: O "Gap" de Concentração (Gini) nas Três Camadas
df_gini = df[(df['metrica'] == 'gini') & (df['orcamento_suborno'] == 0.0)]
plt.figure(figsize=(10, 6))
sns.barplot(data=df_gini, x='distribuicao', y='media', hue='camada', errorbar=None)
plt.title('Salto de Concentração (Gini) entre as Camadas')
plt.ylabel('Coeficiente de Gini (Mais perto de 1 = Mais concentrado)')
plt.xlabel('Distribuição Inicial de Riqueza')
plt.savefig('grafico_gini_camadas.png')
plt.close()

print("Gráficos gerados com sucesso! Verifique os ficheiros PNG na pasta.")