# 📈 Quantitative Swing Trading Research Framework

Framework de investigación cuantitativa en Python orientado al desarrollo, validación y seguimiento prospectivo de estrategias de **swing trading sobre acciones estadounidenses**.

El proyecto comenzó como un scanner técnico experimental basado principalmente en Williams %R, ATR, volumen y tendencia. Desde entonces evolucionó hacia una arquitectura completa de investigación sistemática con:

- backtesting causal;
- portfolio multi-activo;
- position sizing por riesgo;
- validación fuera de muestra;
- falsificación de hipótesis;
- análisis de robustez;
- stress de costes;
- holdout final;
- auditoría de implementación;
- paper trading prospectivo;
- monitoreo de degradación del edge.

> ⚠️ **Este proyecto es experimental y educativo.**
>
> Los resultados históricos no predicen rendimientos futuros.  
> La estrategia actual continúa bajo validación prospectiva mediante paper trading y no debe interpretarse como una recomendación de inversión ni como autorización para operar capital real.

---

# 🧠 Filosofía del proyecto

El objetivo no es encontrar la configuración con mayor rentabilidad histórica.

La prioridad es encontrar una estrategia que:

- tenga una ventaja estadística razonablemente estable;
- sobreviva distintos períodos de mercado;
- no dependa de unos pocos trades extraordinarios;
- tolere costes de ejecución mayores;
- mantenga resultados fuera de muestra;
- evite utilizar información futura;
- pueda reproducirse de manera determinista;
- sea validada posteriormente con datos nunca utilizados durante su desarrollo.

Principio central:


ROBUSTEZ > BACKTEST MÁXIMO


Un máximo aislado en un backtest se considera menos valioso que una región amplia de parámetros con comportamiento consistente.

---

# ⏱️ Causalidad del sistema

El motor está diseñado para evitar look-ahead bias.

La secuencia fundamental es:

CLOSE(T)
   ↓
generación de señal
   ↓
OPEN(T+1)
   ↓
entrada potencial


Una señal generada utilizando el cierre de una rueda solamente puede ejecutarse a partir de la siguiente sesión disponible.

---

# 🎯 Arquitectura congelada actual

Después de múltiples fases de investigación y falsificación, la arquitectura utilizada para la validación prospectiva quedó congelada.

Componentes principales:


Trend
Pullback
RS20
Volume
Candle


Filtros estructurales adicionales:


RS20 >= 1%
ATR_PCT entre 3% y 5%
VolRel >= 1.15


Gestión base:


Take Profit       = 1.8 R
Stop Loss         = 1.5 ATR
Risk / trade      = 0.5% del equity
Max gross exposure= 90%
Portfolio risk    = 2.5%


La arquitectura no debe modificarse utilizando resultados del forward test actual.

Si en el futuro se decide cambiar la estrategia, ese cambio debe formar una **nueva rama experimental** y requerirá una nueva validación con datos futuros.

---

# 🧪 Evolución de la investigación

## V6 — Falsification Lab

Se realizaron experimentos controlados sobre:

- volumen relativo;
- ATR;
- RS20;
- costes;
- concentración;
- sensibilidad del portfolio.

El hallazgo más importante fue la aparición de una región robusta alrededor de:


ATR_PCT ≈ 3% – 5%


en lugar de un único parámetro óptimo.

---

## V7 — Interaction Lab

Se estudiaron interacciones entre los filtros más prometedores.

La combinación:


ATR 3–5%
+
VolRel >= 1.15


mostró una mejora consistente respecto del modelo base.

También se realizaron:

- bootstrap por bloques temporales;
- análisis por semestres;
- eliminación de grandes ganadores;
- stress de costes;
- comparación incremental entre filtros.

---

## V8 — Robustness Lab

La configuración candidata fue sometida a perturbaciones locales.

Se probaron variaciones de:


VolRel
ATR
universo de acciones
costes
concentración


La región alrededor de los parámetros seleccionados permaneció razonablemente estable.

Por este motivo se tomó una decisión importante:


DETENER LA OPTIMIZACIÓN SOBRE 2023–2025


y congelar la arquitectura antes de observar el holdout final.

---

# 🔒 V9 — Final Holdout

El período 2026 fue reservado previamente como conjunto final fuera de muestra.

La arquitectura fue congelada antes de observar sus resultados.

Período evaluado:


2026-01-02 → 2026-09-09


Resultado aproximado:


Return          +17.43%
Profit Factor     1.59
Max Drawdown     -4.60%
Trades              124
Win Rate          49.2%
Avg R            +0.257


Benchmark SPY durante el mismo período:


≈ +12.19%


El sistema sobrevivió los criterios previamente establecidos para el holdout.

Esto **no significa que la estrategia esté garantizada**, solamente que logró sobrevivir una prueba que no había sido utilizada para seleccionar sus parámetros.

---

# 🔬 V10 — Operational Audit

Después del holdout se realizó una auditoría adicional sin modificar la estrategia.

Se analizaron:

- costes adicionales;
- rachas de pérdidas;
- rolling Profit Factor;
- rolling AvgR;
- concentración por ticker;
- simulaciones Monte Carlo;
- límites de exposición;
- sensibilidad operativa.

El sistema continuó siendo positivo incluso bajo distintos niveles de fricción, aunque también aparecieron advertencias importantes:

- deterioro reciente del rolling edge;
- concentración significativa en algunos grandes ganadores.

El resultado fue clasificado como:


PAPER_TRADE_READY_WITH_MONITORING


Esto no equivale a una autorización para operar capital real.

---

# 🧪 V11 — Forward / Shadow Trading

Después de finalizar la investigación histórica se inició la fase prospectiva.

Inicio establecido:


2026-09-10


A partir de esta fecha los nuevos datos son considerados verdaderamente futuros respecto del proceso de desarrollo.

---

## V11.1 — Shadow Engine

`v11_shadow_engine.py`

Implementa la estrategia congelada de manera persistente.

El motor mantiene entre ejecuciones:

- cash;
- posiciones abiertas;
- señales pendientes;
- operaciones;
- equity;
- cooldowns;
- estado del portfolio.

No realiza liquidaciones artificiales simplemente porque termine la ejecución del programa.

Si el programa no se ejecuta durante varias ruedas, procesa cronológicamente las sesiones pendientes cuando vuelve a iniciarse.

---

## V11.2 — Parity Audit

`v11_2_parity_audit.py`

Antes de confiar en el forward engine se realizó una auditoría histórica independiente comparándolo contra el motor canónico.

Resultado:


Reference trades       452
Shadow trades          452

Trade mismatches         0
Equity mismatches        0

Reference PF       1.406478
Shadow PF          1.406478


La implementación prospectiva reprodujo exactamente el comportamiento esperado sobre el período auditado.

Resultado:


PARITY_CONFIRMED


---

## V11.3 — Forward Monitoring & Drift Guard

`v11_3_monitor.py`

El monitor es deliberadamente pasivo.

NO:

- genera nuevas señales;
- cambia parámetros;
- modifica posiciones;
- optimiza la estrategia.

Su función es vigilar el comportamiento del sistema prospectivo.

Controla entre otras cosas:


Profit Factor
AvgR
Drawdown
Rolling PF
Rolling AvgR
Concentración
Caps de portfolio
Integridad de archivos
Causalidad de operaciones


Checkpoints previamente definidos:


25 trades    → diagnóstico temprano
50 trades    → diagnóstico
100 trades   → primera revisión formal
150 trades
+ 183 días   → revisión madura


La estrategia no debe ser retocada simplemente porque aparezca una mala racha durante estas etapas.

---

# 📊 Interpretación correcta de los resultados

Una estrategia puede mostrar un buen backtest y aun así fallar en el futuro.

Existen numerosos riesgos que ningún backtest puede eliminar por completo:

- cambios de régimen;
- gaps;
- correlación entre posiciones;
- survivorship bias;
- diferencias de ejecución;
- deslizamiento;
- cambios en Yahoo Finance;
- concentración;
- degradación estructural del edge.

Por este motivo el proyecto separa explícitamente:


IN-SAMPLE
↓
OUT-OF-SAMPLE
↓
ROBUSTNESS
↓
FINAL HOLDOUT
↓
PAPER TRADING PROSPECTIVO
↓
EVENTUAL VALIDACIÓN REAL


---

# 📁 Estructura principal


bot-acciones/
│
├── main.py
├── research_engine.py
├── strategy.py
├── regime_lab.py
│
├── v6_falsification_lab.py
├── v7_interaction_lab.py
├── v8_robustness_lab.py
├── v9_final_holdout.py
├── v10_operational_audit.py
│
├── v11_shadow_engine.py
├── v11_2_parity_audit.py
├── v11_3_monitor.py
│
├── requirements.txt
├── run.bat
├── .gitignore
└── README.md


Durante la ejecución también pueden crearse:


cache/
results/
__pycache__/


Estos directorios representan datos locales, caches, resultados experimentales o estado de ejecución y no forman parte del código fuente distribuido mediante Git.

---

# ⚙️ Instalación

## 1. Instalar Python

Se recomienda utilizar una versión moderna de Python 3.

Comprobar instalación:


python --version


o en Windows:


py --version


---

## 2. Clonar el repositorio


git clone <https://github.com/Arox43iq/cedear-swing-bot>
cd bot-acciones


También puede descargarse desde GitHub utilizando:


Code → Download ZIP


---

## 3. Crear un entorno virtual

Windows:


python -m venv venv


Activarlo:


venv\Scripts\activate


---

## 4. Instalar dependencias


python -m pip install --upgrade pip
pip install -r requirements.txt


Dependencias principales:

- pandas
- numpy
- yfinance

---

# ▶️ Ejecutar

Desde terminal:


python main.py


En Windows también puede utilizarse:


run.bat


El menú principal permite acceder a los distintos módulos de investigación y seguimiento.

---

# 🛰️ Rutina actual de paper trading

Durante la fase prospectiva se utilizan principalmente:


V11.1 — Shadow / Paper Engine
V11.3 — Forward Monitor


La rutina normal consiste en ejecutarlos después de que cierre el mercado estadounidense y Yahoo Finance haya publicado la nueva vela diaria.

Primero:


V11.1


y después:


V11.3


V11.2 no necesita ejecutarse diariamente porque es una auditoría de paridad ya realizada.

Los laboratorios históricos tampoco deben ejecutarse diariamente para buscar nuevas configuraciones.

---

# 🔐 Integridad experimental

Una regla fundamental del proyecto es:


NO OPTIMIZAR UTILIZANDO EL FUTURO


Los resultados observados durante V11 pertenecen al forward test.

Modificar filtros basándose en ellos y continuar considerando la estrategia como la misma validación invalidaría metodológicamente el experimento.

Cualquier cambio futuro debe documentarse como una nueva versión independiente.


# ⚠️ Disclaimer

Este software fue desarrollado con fines educativos, experimentales y de investigación cuantitativa.

No constituye:

- asesoramiento financiero;
- una recomendación de compra o venta;
- una garantía de rendimiento;
- un sistema infalible de inversión.

Los resultados históricos pueden diferir sustancialmente de los resultados futuros.

Toda decisión financiera y todo riesgo asociado al uso del software son responsabilidad de quien lo utiliza.

---

# 🛠️ Estado actual


Historical research       ✅
Falsification             ✅
Robustness testing        ✅
Final holdout             ✅
Operational audit         ✅
Shadow engine             ✅
Implementation parity     ✅
Forward monitoring        ✅
Prospective validation    🔄 EN CURSO
Real-money validation     ⏳ NO INICIADA

El objetivo actual no es seguir optimizando el pasado.

El objetivo es observar qué ocurre cuando una estrategia completamente congelada se enfrenta a datos que todavía no existían durante su desarrollo.