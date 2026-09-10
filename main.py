from pathlib import Path

from research_engine import run_research_lab, run_directed_lab, run_validation_lab, scan_live
from regime_lab import run_regime_lab
from v6_falsification_lab import run_falsification_lab
from v7_interaction_lab import run_v7_lab
from v8_robustness_lab import run_v8_lab
from v9_final_holdout import run_v9_final_holdout
from v10_operational_audit import run_v10_audit
from v11_shadow_engine import run_v11_shadow
from v11_2_parity_audit import run_v11_2_audit
from v11_3_monitor import run_v11_3_monitor

Path("results").mkdir(exist_ok=True)


def universe_menu(title):
    print("\n" + "=" * 88)
    print(title)
    print("=" * 88)
    print("\n  1️⃣ 🇺🇸 USA (USD)")
    print("  2️⃣ 🇦🇷 CEDEARs (ARS)")
    print("  3️⃣ ↩️ Volver")
    op = input("\n👉 Opción: ").strip()
    return {"1": "USA", "2": "CEDEAR"}.get(op)


def menu():
    print("\n" + "=" * 88)
    print("🧠 TRADING RESEARCH ENGINE — V11.3 FORWARD MONITOR")
    print("=" * 88)
    print("\n  1️⃣  📡 Analizar oportunidades actuales")
    print("  2️⃣  🔬 Backtest / Laboratorio robusto")
    print("  3️⃣  🧪 Laboratorio dirigido anterior")
    print("  4️⃣  🧬 V4 — Validación multiperíodo + simplificación")
    print("  5️⃣  🧠 V5 — Regímenes + descomposición del edge")
    print("  6️⃣  🧪 V6 — Falsificación de calidad de señal")
    print("  7️⃣  🧱 V7 — Interacciones robustas + años independientes")
    print("  8️⃣  🛡️ V8 — Robustez estructural + stress de universo")
    print("  9️⃣  🔒 V9 — Test final 2026 (consumido)")
    print("  10️⃣ 🧰 V10 — Auditoría operativa")
    print("  11️⃣ 🛰️ V11.1 — Shadow/Paper prospectivo")
    print("  12️⃣ 🔎 V11.2 — Auditoría de paridad e integridad")
    print("  13️⃣ 🧭 V11.3 — Monitor prospectivo + drift guard")
    print("  14️⃣ 📊 Ver archivos de resultados")
    print("  15️⃣ 🚪 Salir")
    print("\n" + "=" * 88)


def main():
    while True:
        menu()
        op = input("👉 Seleccioná una opción: ").strip()

        if op == "1":
            u = universe_menu("📡 SCANNER")
            if u:
                scan_live(u)
                input("\n↩️ Enter para volver al menú...")

        elif op == "2":
            u = universe_menu("🔬 LABORATORIO")
            if u:
                run_research_lab(u)
                input("\n↩️ Enter para volver al menú...")

        elif op == "3":
            u = universe_menu("🧪 LABORATORIO DIRIGIDO")
            if u:
                run_directed_lab(u)
                input("\n↩️ Enter para volver al menú...")

        elif op == "4":
            u = universe_menu("🧬 V4 — VALIDACIÓN MULTIPERÍODO")
            if u:
                run_validation_lab(u)
                input("\n↩️ Enter para volver al menú...")

        elif op == "5":
            run_regime_lab("USA")
            input("\n↩️ Enter para volver al menú...")

        elif op == "6":
            run_falsification_lab("USA")
            input("\n↩️ Enter para volver al menú...")

        elif op == "7":
            run_v7_lab("USA")
            input("\n↩️ Enter para volver al menú...")

        elif op == "8":
            run_v8_lab("USA")
            input("\n↩️ Enter para volver al menú...")

        elif op == "9":
            print("\n🔒 V9 ya fue consumido; no usarlo para seleccionar otra variante.")
            run_v9_final_holdout("USA")
            input("\n↩️ Enter para volver al menú...")

        elif op == "10":
            run_v10_audit()
            input("\n↩️ Enter para volver al menú...")

        elif op == "11":
            run_v11_shadow()
            input("\n↩️ Enter para volver al menú...")

        elif op == "12":
            run_v11_2_audit()
            input("\n↩️ Enter para volver al menú...")

        elif op == "13":
            run_v11_3_monitor()
            input("\n↩️ Enter para volver al menú...")

        elif op == "14":
            print("\n📁 ./results/")
            for f in sorted(Path("results").glob("*")):
                if f.suffix.lower() in {".csv", ".json"}:
                    print(f"   • {f.name}")
            input("\n↩️ Enter para volver al menú...")

        elif op == "15":
            print("\n👋 Cerrando research engine.")
            break

        else:
            print("❌ Opción inválida.")


if __name__ == "__main__":
    main()
