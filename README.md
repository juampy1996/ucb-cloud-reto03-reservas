# Reto 03: Sistema de Reservas y Citas (Arquitectura Serverless)

Proyecto final para la materia **Computación en la Nube** (Maestría en Ciencia de Datos e Inteligencia Artificial, UCB).

* **Estudiante:** Juan Pablo Meriles
* **Correo Institucional:** `juan.meriles@ucb.edu.bo`
* **Docente:** Fabrizio Bellido

---

## 🏗️ Arquitectura del Sistema
* **Frontend:** Amazon S3 (Hosting de sitio estático web con interfaz en tiempo real).
* **API Gateway:** HTTP API pública con enrutamiento de peticiones y control de CORS.
* **Backend:** AWS Lambda (Python 3.13 con lógica REST para métodos GET, POST, PUT, DELETE).
* **Persistencia:** Amazon DynamoDB (Tabla bajo demanda con clave de partición compuesta y **escritura condicional** para evitar *overbooking*).
* **Monitoreo:** Amazon CloudWatch (Logs y métricas personalizadas EMF bajo el espacio `UCB/Reservas`).

---

## 🚀 Guía Rápida de Despliegue en AWS
1. **DynamoDB:** Crear tabla `ucb-reservas-jpm` con Partition Key `slot_id` (String).
2. **Lambda:** Crear función `ucb-api-reservas-jpm` (Python 3.13) asignando `LabRole`, variables de entorno (`TABLA_RESERVAS=ucb-reservas-jpm`, `ADMIN_KEY=ucb-admin-2026`) y pegando el código de `backend/lambda_function.py`.
3. **API Gateway:** Crear HTTP API conectada a la función Lambda bajo la ruta `ANY /reservas` con CORS habilitado.
4. **S3:** Crear bucket, habilitar hosting web estático, subir `frontend/index.html` (con la Invoke URL apuntando a `/reservas`) y aplicar la política de lectura pública de `infra/bucket_policy.json`.