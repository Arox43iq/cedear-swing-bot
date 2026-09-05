# 📈 Bot de Swing Trading y Gestión de Riesgo (CEDEARs / BYMA)

Script automatizado en Python que analiza masivamente un universo de 157 activos en la bolsa argentina (CEDEARs), detecta oportunidades técnicas de rebote de alta calidad y calcula de manera automática la gestión de riesgo.

## ✨ ¿Qué hace exactamente?
* **Filtro Macro:** Solo busca compras si el S&P 500 está alcista (Precio > EMA 200).
* **Confluencia Técnica:** Cruza Bandas de Bollinger, StochRSI(7) en mínimos absolutos y volumen exhausto.
* **Blindaje Anti-Earnings:** Descarta automáticamente activos con balances cercanos (menos de 7 días) para evitar riesgos de sorpresas corporativas.
* **Gestión de Riesgo Integrada:** Calcula dinámicamente el **Stop Loss** técnico y el **Take Profit** antes de operar.
* **Autoauditoría:** Evalúa el rendimiento histórico (Win Rate) de las alertas generadas previamente.

---

## ⚙️ Guía de instalación rápida (Paso a Paso)

Si no tenés mucha experiencia con la compu, seguí estos simples pasos para probarlo en tu Windows:

### 1. Requisitos previos
Tené instalado [Python](https://www.python.org/) (asegurate de marcar la casilla *"Add Python to PATH"* durante la instalación).

### 2. Descargar el proyecto
Descargá este repositorio como archivo ZIP desde el botón verde **"Code" > "Download ZIP"** arriba en esta página, y descomprimilo en una carpeta en tu computadora (por ejemplo, en el Escritorio).

### 3. Abrir la terminal
* Entrá a la carpeta descomprimida del proyecto.
* En la barra de direcciones de arriba de la carpeta, borrá todo, escribí `cmd` y apretá **Enter** (se abrirá la terminal negra en esa ruta).

### 4. Instalar las herramientas necesarias
Copiá y pegá este comando en la terminal y apretá Enter:

pip install pandas yfinance
5. Ejecutar el bot
Una vez instalado, escribí el siguiente comando y apretá Enter para ponerlo a correr:

Bash
python main.py
¡Listo! El bot analizará el mercado en segundos y te mostrará el ranking de oportunidades directamente en tu pantalla.

🤝 ¿Querés dar feedback?
Este proyecto está en fase de pruebas. Si lo probaste, se te colgó, o querés sugerir mejoras, podés dejar un comentario en el repositorio o contactarme. ¡Toda crítica constructiva es bienvenida!
