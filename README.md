# 📈 Bot de Swing Trading y Gestión de Riesgo Dinámica (CEDEARs / BYMA)

Script automatizado en Python diseñado para escanear masivamente el universo de CEDEARs en la bolsa argentina (BYMA), combinando análisis técnico institucional, gestión de riesgo adaptativa por volatilidad (ATR + Soportes), análisis fundamental de noticias y un módulo de autoevaluación histórica.

---

##  ¿Qué hace exactamente?

* **🛡️ Escudo Anti-Feriados (EE.UU.):** Valida automáticamente el estado de Wall Street. Si el mercado norteamericano está cerrado o es feriado, el bot pausa las alertas para evitar falsos positivos por el bajo volumen local.
* **🌐 Filtro Macro:** Evalúa el contexto general y prioriza entornos favorables si el S&P 500 se encuentra alcista (Precio > EMA 200).
* **🎯 Confluencia Técnica Avanzada:** Detecta zonas de alta probabilidad cruzando Bandas de Bollinger, Stochastic RSI en mínimos, rechazo de velas alcistas (*Giro de Precio*) y volumen institucional climácico (*Volumen de Giro*).
* **⚠️ Blindaje Anti-Earnings:** Verifica el calendario de balances para evitar operar activos con reportes de ganancias inminentes (menos de 7 días).
* **📰 Contexto Fundamental & Sentimiento:** Extrae automáticamente noticias financieras recientes asociadas a cada activo para evaluar el trasfondo de mercado.
* **⚖️ Gestión de Riesgo Dinámica (Triple Capa):** 
  * Calcula el Stop Loss técnico basándose en el **mínimo de las últimas 60 ruedas** o la tendencia rápida.
  * Integra la volatilidad matemática mediante el **ATR (Average True Range)** para evitar que el ruido del dólar CCL expulse prematuramente al inversor.
  * Aplica un **Piso Absoluto (Tope estricto del 12%)** como salvaguarda final.
* **🎯 Take Profit Inteligente:** Calcula el objetivo de ganancia asegurando de forma estricta un **Ratio Riesgo/Beneficio mínimo de 1.5x**.
* **🧠 Módulo de Automejora (Autoauditoría):** Evalúa el rendimiento histórico y el Win Rate real de las alertas emitidas mediante un filtro temporal estricto.
* **📂 Sincronización Local:** Genera automáticamente archivos estructurados (`oportunidades.csv` e `historial_senales.csv`) para un seguimiento continuo.

---

## 🛠️ Tecnologías y Librerías Utilizadas

* **Python 3.x**
* **yfinance:** Extracción de datos de mercado históricos y cotizaciones en tiempo real.
* **pandas:** Procesamiento de datos y manipulación de estructuras analíticas.

---

## ⚙️ Guía de instalación rápida (Paso a Paso)

Si quieres ponerlo a correr en tu computadora, sigue estos simples pasos:

### 1. Requisitos previos
Asegúrate de tener instalado Python en tu equipo (recuerda marcar la casilla *"Add Python to PATH"* durante su instalación).

### 2. Descargar el proyecto
Puedes clonar el repositorio o descargarlo como archivo ZIP desde el botón verde **"Code" > "Download ZIP"** arriba en esta página, y descomprimirlo en una carpeta en tu computadora.

### 3. Abrir la terminal en la carpeta
* Entra a la carpeta descomprimida del proyecto.
* En la barra de direcciones superior de la carpeta, borra la ruta actual, escribe `cmd` y presiona **Enter** (se abrirá la terminal en esa misma ruta).

### 4. Instalar las herramientas necesarias
Copia y pega este comando en la terminal y presiona **Enter**:

pip install pandas yfinance

### 5. Ejecutar el bot
Una vez instalado, escribe el siguiente comando y presiona Enter para ponerlo a funcionar:


python main.py
¡Listo! El bot analizará el mercado, calculará los niveles dinámicos de riesgo y te mostrará el ranking de oportunidades directamente en tu pantalla.

📁 Estructura del Proyecto
main.py: Script principal que ejecuta el análisis técnico, los cálculos de ATR/Soportes, el filtro fundamental y la gestión de riesgo.

oportunidades.csv: Registro de las oportunidades ideales detectadas en la última ejecución.

historial_senales.csv: Historial acumulado para el seguimiento de aciertos y tropiezos (Módulo de Automejora).

🤝 ¿Querés dar feedback?
Este proyecto está en fase de mejora continua orientada al trading cuantitativo. Si lo probaste, encontraste algún detalle, o querés sugerir mejoras, ¡toda crítica constructiva o aporte en el repositorio es bienvenido!
