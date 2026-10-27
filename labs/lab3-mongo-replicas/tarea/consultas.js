// Tarea 3 — consultas sobre boleteria.eventos (mongosh --file, un solo nodo)
const ev = db.eventos;

function resumen(titulo, cursor) {
  const s = cursor.explain("executionStats");
  const es = s.executionStats;
  // etapa de entrada: la más profunda de winningPlan (IXSCAN o COLLSCAN)
  let p = s.queryPlanner.winningPlan;
  while (p.inputStage) p = p.inputStage;
  print(titulo);
  printjson({
    etapa: p.stage,
    indice: p.indexName || null,
    nReturned: es.nReturned,
    totalDocsExamined: es.totalDocsExamined,
    totalKeysExamined: es.totalKeysExamined,
    executionTimeMillis: es.executionTimeMillis
  });
}

// ---------- A1 ----------
print("== A1 ==");
const filtroA1 = {
  categoria: "concierto", ciudad: "Heredia",
  fecha: { $gte: "2026-12-01", $lte: "2027-02-28" }
};
ev.find(filtroA1, { _id: 0, nombre: 1, recinto: 1, fecha: 1 })
  .sort({ fecha: 1 }).forEach(printjson);

// explain antes / después del índice (se borra para que el script sea repetible)
ev.dropIndexes();
print("== A1 explain ANTES del índice ==");
resumen("sin índice (solo _id)",
  ev.find(filtroA1, { _id: 0, nombre: 1, recinto: 1, fecha: 1 }).sort({ fecha: 1 }));

// igualdad (categoria, ciudad) primero; el rango y el sort comparten fecha al final
print("createIndex: " + ev.createIndex({ categoria: 1, ciudad: 1, fecha: 1 }));
print("== A1 explain DESPUÉS del índice ==");
resumen("con índice {categoria:1, ciudad:1, fecha:1}",
  ev.find(filtroA1, { _id: 0, nombre: 1, recinto: 1, fecha: 1 }).sort({ fecha: 1 }));

// ---------- A2 ----------
print("== A2 ==");
const sinElem = ev.countDocuments({ "zonas.nombre": "VIP", "zonas.precio": { $lt: 48000 } });
const conElem = ev.countDocuments({ zonas: { $elemMatch: { nombre: "VIP", precio: { $lt: 48000 } } } });
print("sin $elemMatch (dos condiciones separadas): " + sinElem);
print("con $elemMatch: " + conElem);
// eventos que solo entran sin $elemMatch (cada condición la cumple una zona distinta)
const soloSinElem = {
  "zonas.nombre": "VIP", "zonas.precio": { $lt: 48000 },
  zonas: { $not: { $elemMatch: { nombre: "VIP", precio: { $lt: 48000 } } } }
};
print("falsos positivos sin $elemMatch: " + ev.countDocuments(soloSinElem));
print("ejemplo de falso positivo:");
ev.find(soloSinElem, { nombre: 1, zonas: 1 }).limit(1).forEach(printjson);
ev.find(
  { zonas: { $elemMatch: { nombre: "VIP", precio: { $lt: 48000 } } } },
  { _id: 0, nombre: 1, zonas: { $elemMatch: { nombre: "VIP", precio: { $lt: 48000 } } } }
).forEach(printjson);

// ---------- A3 ----------
print("== A3 ==");
ev.find(
  { etiquetas: "accesible", categoria: { $nin: ["teatro", "conferencia"] } },
  { _id: 0, nombre: 1, categoria: 1, etiquetas: 1 }
).forEach(printjson);

// ---------- A4 ----------
print("== A4 ==");
ev.aggregate([
  { $match: { patrocinador: { $exists: false } } },
  { $group: { _id: "$categoria", eventos_sin_patrocinador: { $sum: 1 } } },
  { $sort: { _id: 1 } }
]).forEach(printjson);

// ---------- A5 ----------
print("== A5 ==");
ev.aggregate([
  { $unwind: "$zonas" },
  { $group: { _id: "$ciudad", capacidad_total: { $sum: "$zonas.capacidad" } } },
  { $sort: { capacidad_total: -1 } }
]).forEach(printjson);

// ---------- Parte B: tamaño de una orden ----------
print("== B ==");
const orden = {
  _id: "ORD-000001", evento_id: "EV-0001", zona: "General",
  cantidad: 2, estado: "confirmada", creada_en: new Date()
};
const bytes = bsonsize(orden);
print("bsonsize(orden) = " + bytes + " bytes");
print("órdenes en 16 MB (16777216 B), sin contar el resto del evento: " + Math.floor(16777216 / bytes));
print("bsonsize(evento EV-0001) = " + bsonsize(ev.findOne({ _id: "EV-0001" })) + " bytes");
