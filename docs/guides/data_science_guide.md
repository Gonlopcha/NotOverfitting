# 🔬 Guía Cuantitativa: Ciencia de Datos con NotOverfitting

Hacer ciencia de datos financiera no se trata de buscar la combinación mágica que te haga millonario en un backtest. Se trata de **descubrir ineficiencias matemáticas** en el mercado que sean estadísticamente significativas y que sobrevivan al tiempo.

Esta guía detalla el flujo de trabajo científico (Workflow) que debes seguir al usar tu nueva herramienta.

---

## 🎯 Recomendación de Símbolos y Mercados

El Machine Learning ama los datos limpios, los mercados líquidos y los comportamientos predecibles (sea por tendencia o por reversión a la media). No todos los símbolos son aptos.

> [!TIP]
> **Mercados Altamente Recomendados para ML**
> * **EURUSD (Euro / Dólar):** El rey de la liquidez. Sus movimientos son muy "suaves" y respeta muy bien la volatilidad matemática (ATR). Excelente para algoritmos de Triple Barrera.
> * **XAUUSD (Oro):** Tiene tendencias muy prolongadas y direccionales impulsadas por eventos macroeconómicos. Ideal si tu modelo detecta *momentum*.
> * **SP500 / US500 (Índice Bursátil):** Tiene un sesgo estadístico alcista a largo plazo y reversión a la media en correcciones a corto plazo. 

> [!WARNING]
> **Mercados a Evitar al Principio**
> * **Criptomonedas de baja liquidez:** Tienen demasiado ruido, spikes y manipulación.
> * **Pares Exóticos (ej. USDTRY, USDMXN):** Los spreads y comisiones te "comerán" el beneficio matemático de los Take Profits ajustados.

---

## 🔬 Flujo de Trabajo (Paso a Paso)

Sigue estos 5 pasos de forma secuencial cada vez que quieras investigar una nueva hipótesis en el mercado.

### Paso 1: Recolección y Selección (Pestaña "Datos")
1. **Define tu Hipótesis:** ¿Vas a cazar tendencias a mediano plazo? Usa temporalidad **H1** (1 Hora). ¿Buscas reversiones rápidas intra-día? Usa **M15** (15 Minutos).
2. **Descarga masiva:** Selecciona el símbolo (ej. `EURUSD`) y descarga al menos 3 a 5 años de historia. Necesitas capturar diferentes "regímenes" de mercado (alcista, bajista, crisis, lateral) para que la IA no se sesgue a un solo entorno.
3. **Exploración:** Observa el gráfico en la GUI. Cerciórate de que no haya agujeros gigantes en los datos (huecos sin operar).

### Paso 2: Limpieza y Reducción de Ruido (Pestaña "Pipeline")
En los mercados, el precio puro engaña. Necesitamos extraer las "features" matemáticas.
1. **Generación:** Aplica el Pipeline para que calcule el ATR, RSI, Volatilidad, etc.
2. **Reducción (PCA):** Deja activada la opción de PCA (Varianza Explicada al 0.95). 
   > [!NOTE]
   > ¿Por qué el PCA es clave? Porque elimina la "colinealidad". Muchos indicadores dicen exactamente lo mismo de distintas maneras. El PCA comprime esa redundancia en componentes ortogonales que XGBoost procesa mucho más eficientemente, reduciendo drásticamente el ruido.

### Paso 3: Optimización Estricta (Pestaña "Optimización Optuna")
Aquí es donde ocurre la magia, pero también el peligro del sobreajuste (Overfitting).
1. **Selecciona XGBoost:** Es estadísticamente el mejor modelo para datos tabulares.
2. **Walk-Forward Validation:** Configura al menos `3 Folds`. Esto obliga a la IA a entrenar en el año A, probar en el B, luego entrenar en el B y probar en el C. Si un parámetro no sobrevive en todas las ventanas temporales, Optuna lo descarta.
3. **Número de Trials:** Para investigaciones iniciales, usa `20-30 trials`. Para encontrar el modelo definitivo que irá a Live, pon `100 trials` y déjalo procesar.
4. Al finalizar, la IA guardará el cerebro en `models/optimized_production_model.joblib`.

### Paso 4: La Prueba de Fuego (Pestaña "Backtest")
Es el momento de la verdad para saber si tienes una estrategia rentable real.
1. Haz clic en **"Cargar Modelo Guardado"**.
2. **Revisión del Sharpe Ratio:** 
   - Sharpe `< 0.5`: La estrategia es ruido aleatorio. Descarta o busca otro símbolo.
   - Sharpe `0.5 a 1.0`: Estrategia aceptable, pero con curvas de pérdida (drawdowns) sufridas.
   - Sharpe `> 1.0`: Estrategia excelente e invertible.
3. **Revisión de la Equidad:** Revisa si la curva de capital sube en escalera progresiva o si sube por un solo "golpe de suerte" masivo (trade atípico). Un modelo cuantitativo sano gana dinero gradualmente.

### Paso 5: Despliegue en Vivo (Próxima Fase)
Una vez que tienes un modelo con Sharpe > 1.0 en `EURUSD` (por ejemplo), el experimento científico concluye y pasamos a la ejecución mecánica.
El Bot en vivo tomará tu modelo `.joblib` inyectando dinero real (o en cuenta Demo) aplicando ciegamente el Take Profit, el Stop Loss, y cerrando posiciones cada vez que expiren las 24 horas, comportándose exactamente igual que en el laboratorio.
