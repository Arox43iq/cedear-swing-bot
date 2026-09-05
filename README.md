# 📈 CEDEAR & Wall Street Swing Trading Scanner

Un bot cuantitativo automatizado desarrollado en Python para la detección y priorización de oportunidades de compra en **CEDEARs y ETFs** operados en BYMA y Wall Street. Utiliza una estrategia basada en **pullbacks dentro de tendencias alcistas de largo plazo**, combinando análisis técnico avanzado, contexto macroeconómico y noticias fundamentales en tiempo real.

---

## 🚀 Key Features (Características Principales)

* **Filtro de Régimen Macro (`SPY.BA`):** Verifica automáticamente si el S&P 500 se encuentra por encima de su EMA de 200 períodos. Solo habilita oportunidades de compra de alta probabilidad si el entorno general es alcista.
* **Análisis Técnico Multivariable:**
  * **Bandas de Bollinger:** Detecta cuando el precio toca o perfora la banda inferior.
  * **StochRSI (7 períodos):** Mide la sobreventa extrema en el corto plazo.
  * **Volumen Exhausto:** Filtra que el activo tenga un volumen inferior a su promedio de 20 ruedas, señal de agotamiento de la presión vendedora.
* **Contexto Fundamental y Próximos Balances:** Extrae de forma automática las fechas de presentación de resultados (*Earnings*) mediante la API de Yahoo Finance.
* **Análisis de Sentimiento en Noticias:** Clasifica automáticamente los últimos titulares del activo en un semáforo de sentimiento (`🟢 Positivo`, `🔴 Negativo`, `⚪ Neutral`) para evaluar el trasfondo mediático de inmediato.
* **Gestión de Errores Robusta:** Manejo inteligente de excepciones para evitar bloqueos por falta de metadatos en ETFs o tickers especiales.
* **Registro Automatizado (`oportunidades.csv`):** Guarda un historial estructurado cada vez que se detecta una configuración ideal en el mercado.

---

## 📊 ¿Cómo Funciona la Lógica del Escáner?

1. **Escaneo Masivo:** Analiza un universo curado de más de 150 activos de alta liquidez.
2. **Validación de Tendencia:** Se descarta cualquier activo que cotice por debajo de su EMA 200.
3. **Puntuación de Cercanía:** Calcula un ranking de proximidad basado en la distancia a la banda inferior y los niveles de sobreventa del StochRSI.
4. **Reporte por Consola:** Devuelve un Top 10 ordenado con etiquetas de volumen, datos de balances y titulares analizados.

---

## 🛠️ Tecnologías y Librerías Utilizadas

* **Python 3.10+**
* `yfinance` - Extracción de datos de mercado, histórico y fundamentales.
* `pandas` - Procesamiento masivo de datos y cálculos matriciales de indicadores.

---

## ⚙️ Instalación y Uso Local

1. Clonar el repositorio:

   git clone [https://github.com/Arox13iq/cedear-swing-bot.git](https://github.com/Arox13iq/cedear-swing-bot.git)
   cd cedear-swing-bot
Crear y activar un entorno virtual:


python -m venv venv
# En Windows:
venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate
Instalar las dependencias:


pip install -r requirements.txt
Ejecutar el bot:


python main.py
