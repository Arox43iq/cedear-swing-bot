# 📈 Bot de Swing Trading Cuantitativo (Estrategia Larry Williams Pro - CEDEARs / BYMA)

Script automatizado en Python diseñado para escanear masivamente el universo de CEDEARs en la bolsa argentina (BYMA), aplicando una metodología de trading purista basada en Larry Williams para maximizar la efectividad, cazar sobreventas extremas impulsadas por dinero institucional y blindar el capital con gestión de riesgo milimétrica.

---

## 🚀 ¿Qué hace exactamente?

* **🛡️ Escudo Anti-Feriados (EE.UU.):** Valida automáticamente el estado de Wall Street. Si el mercado norteamericano está cerrado o es feriado, el bot pausa las alertas para evitar falsos positivos generados por el bajo volumen y el ruido del mercado local.
* **🌐 Filtro Macro de Tendencia:** Evalúa el contexto general y prioriza entornos favorables comprobando si el S&P 500 (SPY) se encuentra en tendencia alcista (Precio por encima de la EMA de 200).
* **🎯 Confluencia Institucional Larry Williams Pro:** Detecta zonas de alta probabilidad cruzando Williams %R (14) en sobreventa extrema y patrones de rechazo con cierre de vela en el tercio superior.
* **⚡ Filtro de Expansión de Volatilidad (ATR Ratio):** Exige que el rango diario de la vela de giro supere un umbral saludable respecto a su ATR, descartando activos "muertos" o trampas bajistas de baja liquidez.
* **⚠️ Blindaje Anti-Earnings:** Verifica de forma estricta el calendario de balances corporativos para descartar automáticamente cualquier activo que reporte ganancias en menos de 7 días, evitando sorpresas de gaps bajistas.
* **📰 Contexto Fundamental & Sentimiento:** Extrae automáticamente noticias financieras recientes asociadas a cada CEDEAR para evaluar el trasfondo de mercado y el sentimiento general de las noticias.
* **⚖️ Gestión de Riesgo por Volatilidad (ATR):** Calcula los niveles de Stop Loss y Take Profit basándose en el ATR (Average True Range) real del activo (acotado entre un 4% y un 12%), adaptando el riesgo al movimiento diario del papel.
* **🎯 Take Profit Inteligente:** Proyecta automáticamente el objetivo de ganancia asegurando de forma estricta un Ratio Riesgo/Beneficio mínimo de 1.5x.
* **⏳ Salida Estricta por Tiempo (5 Ruedas):** Implementa la regla clásica de Larry Williams de cortar por tiempo aquellas operaciones que no logran despegar tras 5 sesiones bursátiles, liberando capital de manera ágil.
* **🧠 Módulo de Automejora (Autoauditoría):** Evalúa de forma autónoma el rendimiento histórico y el Win Rate real de las señales emitidas mediante un registro persistente.
* **📂 Sincronización Local:** Genera automáticamente archivos estructurados (`historial_senales_williams_pro.csv`) para realizar un seguimiento continuo de los aciertos, tropiezos y expiraciones temporales.

## 🚀 Guía Operativa: Cómo operar con el Sistema

Este bot no es una herramienta de ejecución ciega, sino un **generador cuantitativo de alta probabilidad** diseñado bajo la metodología de Larry Williams, complementado con un flujo de validación institucional. 

Para operar una señal con éxito, seguí este proceso de 3 pasos:

### 1️⃣ Paso 1: Escaneo Cuantitativo (El Bot)
Ejecutá el script principal para obtener el ranking actualizado de CEDEARs:
* El bot evalúa automáticamente el **Williams %R (14)** en busca de sobreventa extrema.
* Aplica el filtro de tendencia macro (**EMA 200**), la expansión de volatilidad (**ATR**) y el **Escudo Anti-Feriados / Anti-Earnings**.
* Te devuelve un Top 10 con los activos más aptos junto a sus niveles matemáticos exactos de **Stop Loss** y **Take Profit**.

### 2️⃣ Paso 2: Validación Visual SMC (El Doble Chequeo)
Antes de comprometer capital, tomá el activo que encabeza el ranking y abrilo en tu plataforma de gráficos (TradingView / Cocos Capital) aplicando un indicador de **Smart Money Concepts (SMC)**:
* **Verificá la estructura:** Comprobá que el Stop Loss calculado por el bot coincida o esté protegido detrás de un **Order Block** o soporte institucional clave.
* **Confirmo el objetivo:** Asegurate de que el Take Profit tenga espacio lógico antes de chocar con una resistencia macro de oferta.

### 3️⃣ Paso 3: Ejecución y Luz Verde
* Si la matemática fría del bot y la estructura visual del gráfico confluyen perfectamente (el activo está sobrevendido, respeta la tendencia y apoya en una zona institucional), **se da luz verde para ejecutar la orden** en el broker.
* Respetá siempre la gestión de riesgo dictada por el ATR.
---


⏱️ Nota importante sobre el tiempo de ejecución
Cuando ejecutes python main.py, notarás que la terminal puede demorar entre 7 y 12 minutos en completar todo el proceso. ¡Es totalmente normal y el script no se colgó!

Esto sucede porque el bot procesa masivamente todo el universo de CEDEARs y, para cada activo, realiza de forma secuencial una consulta web segura a Yahoo Finance para descargar el historial técnico, calcular indicadores complejos, verificar el calendario de balances y extraer las últimas noticias financieras. La paciencia vale la pena para obtener un análisis institucional 100% depurado.
---

## ⚙️ Guía de instalación rápida (Paso a Paso para principiantes)

Si quieres ponerlo a correr en tu computadora desde cero, sigue estos simples pasos:

### 1. Requisitos previos
Asegúrate de tener instalado Python en tu equipo (recuerda marcar la casilla *"Add Python to PATH"* durante su instalación para que funcione desde cualquier terminal).

### 2. Descargar el proyecto
Puedes clonar el repositorio o descargarlo como archivo ZIP desde el botón verde **"Code" > "Download ZIP"** arriba en esta página, y descomprimirlo en una carpeta de tu computadora.

### 3. Abrir la terminal en la carpeta del proyecto
* Entra a la carpeta descomprimida del proyecto.
* En la barra de direcciones superior de la ventana de tu explorador de archivos, borra la ruta actual, escribe `cmd` y presiona **Enter** (se abrirá la terminal directamente en esa ruta).

### 4. Instalar las herramientas necesarias
Copia y pega este comando en la terminal que se abrió y presiona **Enter**:

pip install pandas yfinance
### 5. Ejecutar el bot
Una vez instaladas las dependencias, escribe el siguiente comando y presiona Enter para ponerlo a funcionar:

Bash
python main.py
¡Listo! El bot analizará el mercado de forma automática, validará el estado de Wall Street, calculará los niveles de riesgo profesional y te mostrará el ranking de oportunidades directamente en tu pantalla.

📁 Estructura del Proyecto
main.py: Script principal que ejecuta el análisis técnico avanzado, filtros de volumen institucional, control macro, scraping de noticias y gestión de riesgo por ATR.

historial_senales_williams_pro.csv: Historial acumulado generado de forma automática para el seguimiento de aciertos, tropiezos y expiraciones por tiempo (Módulo de Automejora).

## 🛠️ Tecnologías y Librerías Utilizadas

* **Python 3.x**
* **yfinance:** Extracción de datos de mercado históricos, calendario de balances y cotizaciones en tiempo real.
* **pandas:** Procesamiento de datos masivos y manipulación de estructuras analíticas.

🤝 ¿Querés dar feedback?
Este proyecto está en constante evolución dentro del ámbito del trading cuantitativo y sistemático. Si lo probaste, encontraste algún detalle o querés sugerir mejoras, ¡toda crítica constructiva o aporte mediante un Pull Request en el repositorio es más que bienvenido!
