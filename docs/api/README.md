# Contrato de la API REST

- `openapi.json`: contrato exportado con `python -m scripts.exportar_openapi`.
- Swagger UI activo en `/docs` y OpenAPI en `/api/openapi.json` de la aplicación en ejecución.
- Autenticación de demostración: encabezado `Authorization: Bearer <token>` (ver README).
- Errores del negocio: `{"detalle": "mensaje"}` con 401, 403, 404, 409 o 422 (Arquitectura §10).
