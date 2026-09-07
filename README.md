# 📈 Bot de Swing Trading Cuantitativo (Estrategia Larry Williams Pro - CEDEARs / BYMA)

Script automatizado en Python diseñado para escanear masivamente el universo de CEDEARs en la bolsa argentina (BYMA), aplicando una metodología de trading purista basada en **Larry Williams** para maximizar la efectividad, cazar sobreventas extremas impulsadas por dinero institucional y blindar el capital con gestión de riesgo milimétrica.

---

## 🚀 ¿Qué hace exactamente?

* **🛡️ Escudo Anti-Feriados (EE.UU.):** Valida automáticamente el estado de Wall Street. Si el mercado norteamericano está cerrado o es feriado, el bot pausa las alertas para evitar falsos positivos generados por el bajo volumen y el ruido del mercado local.
* **🌐 Filtro Macro de Tendencia:** Evalúa el contexto general y prioriza entornos favorables comprobando si el S&P 500 (`SPY`) se encuentra en tendencia alcista (Precio por encima de la EMA de 200).
* **🎯 Confluencia Institucional Larry Williams Pro:** Detecta zonas de alta probabilidad cruzando **Williams %R (14) en sobreventa extrema**, **Money Flow (Flujo de Dinero Institucional)** y patrones de rechazo con cierre de vela en el tercio superior.
* **⚠️ Blindaje Anti-Earnings:** Verifica de forma estricta el calendario de balances corporativos para descartar automáticamente cualquier activo que reporte ganancias en menos de 7 días, evitando sorpresas de *gaps* bajistas.
* **📰 Contexto Fundamental & Sentimiento:** Extrae automáticamente noticias financieras recientes asociadas a cada CEDEAR para evaluar el trasfondo de mercado y el sentimiento general de las noticias.
* **⚖️ Gestión de Riesgo por Volatilidad (ATR):** Calcula los niveles de Stop Loss y Take Profit basándose en el **ATR (Average True Range)** real del activo, adaptando el riesgo al movimiento diario del papel en lugar de usar porcentajes fijos arbitrarios.
* **🎯 Take Profit Inteligente:** Proyecta automáticamente el objetivo de ganancia asegurando de forma estricta un **Ratio Riesgo/Beneficio mínimo de 1.5x**.
* **🧠 Módulo de Automejora (Autoauditoría):** Evalúa de forma autónoma el rendimiento histórico y el *Win Rate* real de las señales emitidas mediante un registro persistente.
* **📂 Sincronización Local:** Genera automáticamente archivos estructurados (`historial_senales_williams_pro.csv`) para realizar un seguimiento continuo de los aciertos (*Take Profit*) y tropiezos (*Stop Loss*).

---

## 🛠️ Tecnologías y Librerías Utilizadas

* **Python 3.x**
* **yfinance:** Extracción de datos de mercado históricos, calendario de balances y cotizaciones en tiempo real.
* **pandas:** Procesamiento de datos masivos y manipulación de estructuras analíticas.

---

## ⚙️ Guía de instalación rápida (Paso a Paso para principiantes)

Si quieres ponerlo a correr en tu computadora desde cero, sigue estos simples pasos:

### 1. Requisitos previos
Asegúrate de tener instalado **Python** en tu equipo (recuerda marcar la casilla *"Add Python to PATH"* durante su instalación para que funcione desde cualquier terminal).

### 2. Descargar el proyecto
Puedes clonar el repositorio o descargarlo como archivo ZIP desde el botón verde **"Code" > "Download ZIP"** arriba en esta página, y descomprimirlo en una carpeta de tu computadora.

### 3. Abrir la terminal en la carpeta del proyecto
* Entra a la carpeta descomprimida del proyecto.
* En la barra de direcciones superior de la ventana de tu explorador de archivos, borra la ruta actual, escribe `cmd` y presiona **Enter** (se abrirá la terminal directamente en esa ruta).

### 4. Instalar las herramientas necesarias
Copia y pega este comando en la terminal que se abrio y presiona **Enter**:

pip install pandas yfinance
### 5. Ejecutar el bot
Una vez instaladas las dependencias, escribe el siguiente comando y presiona Enter para ponerlo a funcionar:


python main.py


¡Listo! El bot analizará el mercado de forma automática, validará el estado de Wall Street, calculará los niveles de riesgo profesional y te mostrará el ranking de oportunidades directamente en tu pantalla.

📁 Estructura del Proyecto
main.py: Script principal que ejecuta el análisis técnico avanzado, filtros de volumen institucional, control macro, scraping de noticias y gestión de riesgo por ATR.

historial_senales_williams_pro.csv: Historial acumulado generado de forma automática para el seguimiento de aciertos y tropiezos (Módulo de Automejora).

🤝 ¿Querés dar feedback?
Este proyecto está en constante evolución dentro del ámbito del trading cuantitativo y sistemático. Si lo probaste, encontraste algún detalle o querés sugerir mejoras, ¡toda crítica constructiva o aporte mediante un Pull Request en el repositorio es más que bienvenido!
