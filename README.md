# 📈 Bot de Swing Trading y Gestión de Riesgo (CEDEARs / BYMA)

Script automatizado desarrollado en Python que analiza masivamente el universo de CEDEARs en la bolsa argentina, incorporando filtros institucionales, análisis de sentimiento de noticias, gestión de riesgo estricta y autoevaluación histórica.

## ✨ ¿Qué hace exactamente?

* **🛡️ Escudo Anti-Feriados (EE.UU.):** Validación automática del estado de Wall Street. Si el mercado norteamericano está cerrado o es feriado, el bot pausa el registro de nuevas señales para evitar falsos positivos causados por el volumen local.
* **🌐 Filtro Macro:** Evalúa el contexto general y prioriza entornos favorables si el S&P 500 está alcista (Precio > EMA 200).
* **confluencia Técnica Avanzada:** Cruza Bandas de Bollinger, *Stochastic RSI(7)* en mínimos absolutos, rechazo de velas alcistas y volumen climático.
* **⚠️ Blindaje Anti-Earnings:** Descarta o advierte automáticamente sobre activos con balances cercanos (menos de 7 días) para evitar riesgos por sorpresas corporativas.
* **📰 Contexto Fundamental & Sentimiento:** Extracción automática de noticias financieras recientes asociadas a cada activo.
* **⚖️ Gestión de Riesgo Integrada:** Calcula dinámicamente el *Stop Loss* técnico (con un tope máximo del 5% o ajuste por volatilidad) y el *Take Profit* optimizado antes de operar.
* **🧠 Módulo de Automejora (Autoauditoría):** Evalúa el rendimiento histórico y el *Win Rate* real de las alertas generadas previamente mediante un filtro temporal estricto (solo evalúa velas posteriores a la emisión de la señal).
* **📂 Sincronización Local:** Generación automática de archivos estructurados (`oportunidades.csv` e `historial_senales.csv`) para seguimiento continuo.

## 🛠️ Tecnologías y Librerías Utilizadas

* **Python 3.x**
* `yfinance`: Extracción de datos de mercado históricos y actuales.
* `pandas`: Procesamiento de datos y manipulación de DataFrames.

## ⚙️ Guía de instalación rápida (Paso a Paso)

Si quieres ponerlo a correr en tu computadora (Windows), sigue estos simples pasos:

### 1. Requisitos previos
Asegúrate de tener instalado **Python** en tu equipo (recuerda marcar la casilla *"Add Python to PATH"* durante su instalación).

### 2. Descargar el proyecto
Puedes clonar el repositorio o descargarlo como archivo ZIP desde el botón verde **"Code" > "Download ZIP"** arriba en esta página, y descomprimirlo en una carpeta en tu computadora.

### 3. Abrir la terminal en la carpeta
* Entra a la carpeta descomprimida del proyecto.
* En la barra de direcciones superior de la carpeta, borra la ruta actual, escribe `cmd` y presiona **Enter** (se abrirá la terminal negra en esa misma ruta).

### 4. Instalar las herramientas necesarias
Copia y pega este comando en la terminal y presiona Enter:

pip install pandas yfinance
### 5. Ejecutar el bot
Una vez instalado, escribe el siguiente comando y presiona Enter para ponerlo a correr:

python main.py
¡Listo! El bot analizará el mercado en segundos, generará los reportes y te mostrará el ranking de oportunidades directamente en tu pantalla.

!📁 Estructura del Proyecto
main.py: Script principal que ejecuta el análisis técnico, fundamental y de riesgo.

oportunidades.csv: Registro de las oportunidades ideales detectadas en la última ejecución.

historial_senales.csv: Historial acumulado para el seguimiento de aciertos y tropiezos (Módulo de Automejora).

🤝 ¿Querés dar feedback?
Este proyecto está en fase de pruebas y mejora continua. Si lo probaste, encontraste algún detalle, o querés sugerir mejoras, ¡toda crítica constructiva o aporte en el repositorio es bienvenido!
