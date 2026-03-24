# Conclusiones - Práctica LLMs para Biomedicina

**Nombre:**
**Fecha:**

---

## Ejercicio 1: Primera Llamada

### 1. Diferencia entre respuesta sin y con system instruction
La respuesta del modelo se adapta mucho más al contexto que le damos con el system instruction. Por ejemplo, en la parte A, el modelo responde de forma general, mientras que en las partes B y C toma el rol que le atribuimos y 
adapta la respuesta a las instrucciones que le dimos, teniendo mucho más 
tacto y siendo mucho menos técnico en su explicación.

### 2. ¿Pudiste modificar los parámetros internos del modelo? ¿Qué sí controlaste?
No pude modificar los parámetros internos del modelo ya que esos son parte "interna" del propio modelo, y no usé ningún tipo de aclaración para modificar el valor de algún parámetro estándar (si es que eso es posible), pero sí pude controlar el contexto y el rol que toma el modelo a través del system instruction.

### 3. ¿Qué pasaría si cambiaras el rol en el system instruction?
La respuesta generada se adaptaría a ese rol y contexto que le di al modelo.

### 4. ¿Qué system instruction sería útil para tu campo de estudio?
Que el modelo evite a toda costa hacer diagnósticos o recomendar el uso de medicamentos, y que siempre aclare que no es un profesional de la salud y que sus respuestas no deben ser tomadas como consejo médico.

---

## Ejercicio 2: Hiperparámetros

### 1. ¿Qué temperature usarías para un informe médico? ¿Y para brainstorming?
Para un informe médico utilizaría una temperatura cercana a 0. Al ver el ejemplo de la parte A  me di cuenta que al aumentar la temperatura el modelo comienza a usar palabras muy técnicas y complicadas, dificultando la comprensión del texto. En un informe médico buscaría precisión.
Para el brainstorming uno esperaría tener creatividad, por lo tanto la temperatura debería ser más cercana a 2, para que el modelo pueda generar ideas más innovadoras y disruptivas.

### 2. ¿Qué pasó con maxOutputTokens=50? ¿Fue útil?
La respuesta se corta en el límite de Tokens que le pusimos. Yo pensé que el modelo iba a entender que tenía una cantidad de Tokens limitados e iba a redondear la respuesta teniendo en cuenta esa limitación, pero al parecer el modelo en el fondo genera una respuesta y simplemente la corta cuando llega al límite de Tokens. No fue para nada útil la respuesta. Lo mismo aplicaría para los otros 2 casos, aunque en la respuesta más larga se puede obtener mucha información a pesar de que se corte al final.

### 3. Diferencia entre topP bajo y alto
La diferencia entre topP bajo y alto es que en el bajo se tiene en cuenta las opciones que den una probabilidad acumulada menor que ese número bajo, entonces el modelo tiene en cuenta pocas opciones de siguiente palabra. En cambio al tener un valor alto, hay una mayor cantidad de opciones por lo que debería ser un texto más "creativo" o "variado".
Sin embargo, no noté diferencias significativas en los textos escritos, lo mismo con topK bajo vs topK alto. Siento que todos los casos transmitían lo mismo sin variar tanto las palabras, aunque eventualmente se veían algunas palabras más "raras" en los casos de topP y topK alto.

### 4. ¿Las respuestas con temperature=0 fueron idénticas? Implicancias para reproducibilidad
Si, todas las respuestas con temperature=0 en la parte E fueron idénticas. Esto verifica que si se quieren tener resultados predecibles y reproducibles, se debe usar una temperature=0. Esto nos "garantiza" hasta cierto punto que si 2 pacientes hacen la misma pregunta, recibirán la misma respuesta y se disminuirá la probabilidad de interpretaciones cruzadas.

### 5. Hiperparámetros ideales para un chatbot médico. Justificá.
Para un chatbot médico utilizaría una temperature cercana a 0, topP y topK bajos y un maxOutputTokens bajo o moderado, para no sobrecargar de información al paciente y que la respuesta sea precisa y clara. Al ver el ejemplo de la parte A me di cuenta que al aumentar la temperatura el modelo comienza a usar palabras muy técnicas y complicadas, dificultando la comprensión del texto. En un informe médico buscaría precisión, claridez y reproducibilidad.

---

## Ejercicio 3: Prompt Engineering

### 1. Ranking de técnicas (peor a mejor) con justificación
1. Few-shot: me gustó mucho el formato que se eligió y lo siguió al pie de la letra.
2. Chain-of-thought: me gustó mucho el formato y el razonamiento paso a paso, pero al ser tantos pasos se hizo muy largo y poco práctico.
3. Role + constraints: tuvo una excelente respuesta, brindando múltiples posibilidades, pero el formato de la respuesta no presenta utilidad ya que se hace ilegible, debería convertirse esta respuesta a otro formato para aprovechar su potencial.
4. Zero-shot: dio un buen resultado pero al no tener nada que lo encasille, se fue por las ramas, aunque logró dar un buen diagnóstico.

### 2. ¿La respuesta JSON fue clínicamente correcta? Ventajas del output estructurado
Si, la respuesta fue clinicamente correcta. Las ventajas del output estructurado es que permite que el modelo pueda "expresarse" en formatos que le son familiares, por lo tanto debe permitir que el modelo pueda dar respuestas más precisas y claras.

### 3. ¿El chain-of-thought cambió el diagnóstico o solo el razonamiento?
No cambió el diagnóstico, lo que cambió fue que se explayó en una forma muy extensa acerca del razonamiento por el cual se obtuvo ese diagnóstico.

### 4. ¿Encontraste información incorrecta presentada con confianza? ¿Cómo mitigarlo?
No encontré información incorrecta presentada con confianza a primera vista. Al no ser un experto en el tema, no puedo asegurar que no haya información incorrecta, pero sí puedo decir que la información presentada fue consistente con lo que se espera en un caso clínico de este tipo. En caso de que haya información incorrecta, se podría mitigar al regular la temperatura del modelo, u otros hiperparámetros. Por ejemplo, usar una temperatura de cero.

### 5. Tu diseño ideal de asistente diagnóstico
Usaría un asistente que de respuestas reproducibles y certeras, por ejemplo utilizando una temperatura de cero. Además, me gusta que de respuestas esctructuradas y cortas, como en el caso de "few-shot". Esto permite que el paciente pueda ver los resultados de una manera rápida. Por sobre esa base, agregaría que el modelo describa un poco el proceso de pensamiento, al menos indicando las conclusiones que obtiene a partir de ciertos valores del estudio y justificando esos pensamientos. Eso es lo que intenté plasmar en mi prompt personalizado: diagnóstico estructurado, rápido de leer y justificación para quienes quieran profundizar.

---

## Reflexión Final

### ¿Qué aprendiste que no esperabas?
Aprendí cómo el prompt engineering me permite obtener respuestas más precisas y útiles usando diferentes técnicas. Aprendí que, si bien los hiperparámetros modifican las respuestas de los modelos, la respuesta "base" sigue siendo bastante parecida. Aprendí que la regulación de estos detalles puede hacer una gran diferencia en la obtención de un producto final, que se adapte mucho más a las necesidades específicas de un producto o aplicación.

### ¿Qué riesgos ves en el uso de LLMs en medicina?
Principalmente que pueden generar información incorrecta o engañosa. Por eso, es importante regular el uso de LLMs en medicina y establecer pautas claras para su implementación.
Otro riesgo (que no sería el fin del mundo) son las respuestas excesivamente largas que diluyan los resultados obtenidos, creo que la mejor forma de mitigarlo es mediante el uso de prompts bien estructurados y con restricciones claras. 

### ¿Qué oportunidades ves para tu área de especialización?
Se me ocurren 2 posibles aplicaciones: 
Opción 1: que un médico obtenga una segunda opinión rápidamente para poder evaluar posibles diagnósticos. Para esto es importante el orden: que el médico llegue a una conclusión rápida, y que el modelo lo asista para confirmar su diagnóstico, o tener en cuenta posibilidades que puede haber pasado por alto.
Opción 2: que el paciente obtenga explicaciones claras y concisas acerca de su diagnóstico, sin necesidad de sacar un turno médico, ahorrando tiempo tanto al paciente como al médico.
