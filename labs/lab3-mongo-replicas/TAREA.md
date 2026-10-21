# Tarea 3 — Consultas, modelado y un conjunto de cinco miembros

**Valor:** 1,5 % del curso · **Equipos:** los mismos del Laboratorio 3  
**Entrega:** domingo 1 de noviembre de 2026, 11:00 pm, un PDF por equipo (máximo 3 páginas) en TEC Digital, con el enlace al repositorio.  
**Prerrequisito:** Laboratorio 3 completo hasta el Paso 13 (conjunto `rs-lab3` funcionando y semilla cargada).

La tarea extiende el laboratorio en tres direcciones que el Proyecto 2 va a necesitar: **consultar** documentos con el lenguaje de MongoDB, **decidir** entre documentos embebidos y referencias, y **razonar** sobre la mayoría cuando cambia el tamaño del conjunto. Usa la misma boletería del laboratorio; no use el dominio del proyecto.

Toda la evidencia va en `evidence/tarea3/`, con marca de tiempo (`date --iso-8601=seconds`), y cada cifra del PDF debe salir de un archivo de ahí.

---

## Parte A — Consultas sobre la boletería (40 puntos)

Escriba **un archivo** `labs/lab3-mongo-replicas/tarea/consultas.js` que se ejecute completo con:

```bash
mkdir -p evidence/tarea3
docker exec -i ti4601-mongo-1 mongosh --quiet \
  "mongodb://mongo-1:27017,mongo-2:27017,mongo-3:27017/boleteria?replicaSet=rs-lab3" \
  < labs/lab3-mongo-replicas/tarea/consultas.js | tee evidence/tarea3/consultas.txt
```

La URI con `replicaSet` hace que `mongosh` encuentre siempre al primario, aunque `mongo-1` sea secundario: las ventas y los `createIndex` de abajo son escrituras y solo el primario las acepta. Explique en el PDF qué pasaría si se conectara directamente a un secundario.

Cada consulta imprime un encabezado (`print("== A1 ==")`) y su resultado. Use **solo** proyecciones necesarias; no imprima documentos completos.

| # | Pregunta | Operadores que debe usar |
| --- | --- | --- |
| A1 | Nombre, recinto y fecha de los conciertos de Heredia entre el 1 de diciembre de 2026 y el 28 de febrero de 2027, ordenados por fecha | `find`, rango sobre `fecha`, `sort`, proyección |
| A2 | Eventos que tienen zona **VIP** con precio menor a 48 000 colones; muestre nombre y solo la zona VIP | `$elemMatch` en el filtro y en la proyección (o `$`) |
| A3 | Eventos con la etiqueta `"accesible"` que **no** sean ni `"teatro"` ni `"conferencia"` | `$nin`, consulta sobre arreglo |
| A4 | Cantidad de eventos **sin** patrocinador, por categoría | `$exists`, `aggregate` con `$group` |
| A5 | Ocupación por ciudad: capacidad total, entradas vendidas y porcentaje vendido, de mayor a menor porcentaje | `$unwind`, `$group`, `$project`, `$sort` |
| A6 | Las 5 zonas más caras de toda la base, con el nombre del evento al que pertenecen; en caso de empate de precio, ordene por `_id` del evento | `$unwind`, `$sort` por dos campos, `$limit` |

**Ventas para A5.** La semilla no tiene entradas vendidas (`disponibles = capacidad`), así que A5 daría 0 %. Antes de A5, escriba en `consultas.js` tres llamadas `updateOne` que vendan entradas de tres eventos de **ciudades distintas**, usando el mismo filtro con `$elemMatch` y el `$inc` posicional del TODO 3. Imprima `modifiedCount` de cada una y muéstrelas en el PDF. Como el archivo se ejecuta varias veces, explique qué pasa con esas ventas en cada ejecución y cómo lo resolvió (por ejemplo, volviendo a cargar la semilla con `cargar.py` antes de correr el archivo).

Para **A1** y **A3**, incluya `explain("executionStats")` y diga si usan alguno de los índices del laboratorio. Si A3 no usa índice, proponga uno, créelo y muestre el cambio en `totalDocsExamined`. Explique por qué un índice sobre un arreglo (`etiquetas`) se llama **multiclave** y qué costo agrega a cada escritura.

---

## Parte B — Un conjunto de cinco miembros (40 puntos)

En el laboratorio tuvo tres miembros: con uno caído hubo servicio; con dos, no. Ahora va a comprobar qué cambia con cinco.

### B1. Infraestructura (10)

Cree el archivo `labs/lab3-mongo-replicas/tarea/compose.tarea.yml` con **dos miembros más** (`mongo-4` y `mongo-5`) que se unan al conjunto existente. Requisitos:

- mismo `--replSet`, misma red `ti4601`, volumen propio por miembro y el mismo límite de caché;
- se levanta **junto** al Compose del curso, sin modificarlo:

  ```bash
  docker compose -f docker-compose.yml -f labs/lab3-mongo-replicas/tarea/compose.tarea.yml \
    --profile lab3 up -d mongo-4 mongo-5
  ```

- los miembros se agregan con `rs.add()` desde el primario, **uno a la vez**, esperando a que cada uno llegue a `SECONDARY` antes de agregar el siguiente.

Evidencia: `rs-5-miembros.txt` con `rs.status()` (nombre, estado, `health`) y `rs.conf()` (`votes`, `priority`) de los cinco.

### B2. Predicción y prueba (20)

**Antes de ejecutar**, escriba en el PDF una tabla con su predicción para cada fila:

| Miembros caídos | ¿Hay primario? | ¿`w:"majority"` confirma? | ¿`w:1` confirma? |
| --- | --- | --- | --- |
| 1 secundario |  |  |  |
| 2 secundarios |  |  |  |
| el primario y 1 secundario |  |  |  |
| 3 secundarios |  |  |  |

Después ejecute **dos** de las filas: la de **2 secundarios** y la de **3 secundarios**, cada una con la sonda del laboratorio (`sonda_escrituras.py`, `--w majority --duration 60`) y `verificar_rpo.py`, siguiendo el método del laboratorio (precondición, evento, medición, verificación). Use nombres de archivo propios (`t3-dos.*`, `t3-tres.*`). Restaure los miembros detenidos unos 25 s después de la falla, para que la sonda alcance a observar la recuperación.

> La URI del contenedor `app-mongo` solo lista `mongo-1`…`mongo-3`. Pásele una URI con los cinco miembros (`-e MONGO_URI=...` en `docker compose run`), o explique en el PDF por qué con la URI original el driver igual descubre los cinco y qué riesgo tiene si los tres miembros listados están caídos.

Compare la tabla predicha con lo observado y explique cada diferencia.

### B3. Cuatro miembros (10)

Sin ejecutarlo, responda con un argumento de mayoría: ¿por qué un conjunto de **cuatro** miembros votantes no tolera más fallas que uno de tres, y cuesta un miembro más? ¿En qué caso real tendría sentido un cuarto miembro **sin voto** (`votes: 0, priority: 0`)? ¿Qué es un **árbitro** y por qué la documentación de MongoDB desaconseja usarlo con `w:"majority"`?

Al terminar, **retire** `mongo-4` y `mongo-5` con `rs.remove()` y deje el conjunto con tres miembros sanos. Evidencia: `rs-restaurado.txt`.

---

## Parte C — Embeber o referenciar (20 puntos)

En la boletería, las órdenes viven en una colección aparte (`ordenes`) y las zonas viven **dentro** del evento. Un compañero propone guardar también cada orden como un elemento de un arreglo `ordenes` dentro del documento del evento, «para que la compra sea un solo `update` y no necesite idempotencia».

Responda en **una página como máximo**, con números:

1. Estime el tamaño de un documento de evento con 20 000 órdenes embebidas (mida el tamaño real de una orden con `Object.bsonsize()` en `mongosh`) y compárelo con el límite de 16 MB por documento. ¿Cuántas órdenes caben?
2. ¿Qué pasa con la concurrencia cuando cientos de compradores escriben el **mismo** documento? ¿Y con lo que se replica por el oplog en cada compra?
3. ¿Es cierto que la versión embebida no necesita idempotencia? Use lo que observó en la Falla C del laboratorio.
4. Dé una regla general (en una o dos oraciones) para decidir cuándo embeber y cuándo referenciar, y aplíquela a **un** ejemplo de otro dominio que no sea la boletería ni el proyecto.

---

## Entregable

- PDF de **máximo 3 páginas** con las partes A, B y C.
- En el repositorio: `labs/lab3-mongo-replicas/tarea/consultas.js`, `labs/lab3-mongo-replicas/tarea/compose.tarea.yml` y `evidence/tarea3/` (`consultas.txt`, `rs-5-miembros.txt`, `t3-dos.*`, `t3-tres.*`, `rs-restaurado.txt`).
- Commits de los tres integrantes.

## Rúbrica (100 puntos, se escala a 1,5 %)

| Criterio | Pts | Cómo se obtiene el máximo |
| --- | --- | --- |
| A1–A6 correctas | 25 | el archivo corre completo y cada resultado responde la pregunta, con proyecciones mínimas |
| Índices y `explain` | 15 | A1 y A3 explicadas; índice propuesto con antes/después; multiclave explicado |
| Cinco miembros | 10 | `compose.tarea.yml` sin tocar el Compose del curso; `rs.add` uno a uno; evidencia |
| Predicción y prueba | 20 | tabla predicha antes de ejecutar; dos escenarios con sonda, RTO/RPO y comparación honesta |
| Cuatro miembros y árbitros | 10 | argumento de mayoría correcto; caso real de miembro sin voto; riesgo del árbitro |
| Embeber o referenciar | 20 | cálculo con `bsonsize`, concurrencia y oplog, idempotencia y regla aplicada a otro dominio |

**Topes.** Cifras sin archivo en `evidence/tarea3/`: no se puntúan. Modificar `docker-compose.yml` del curso en lugar de usar `compose.tarea.yml`: Cinco miembros en 0. Conjunto entregado con más o menos de tres miembros sanos: −10.
