# Cashflow

Complemento global de NVDA para gestionar pagos desde una interfaz accesible.

## Estado

Primera entrega funcional:

- `GlobalPlugin` para NVDA 2026.1.1;
- menu Herramientas > Cashflow;
- gesto por defecto `NVDA+control+f`;
- doble pulsacion del gesto para abrir el alta de pago;
- dialogo principal con acciones;
- dialogo para cargar pagos;
- listas de pendientes y abonados del mes;
- registro de pagos en SQLite dentro de `globalVars.appArgs.configPath/cashflow/cashflow.db`.
- SQLite vendorizado en `addon/globalPlugins/cashflow/sqlite313/` para evitar conflictos con otros add-ons que modifiquen `sys.path`.

El cifrado de payloads queda planificado como segunda parte. Esta entrega prioriza UI funcional y persistencia local SQLite.

## Uso en scratchpad de NVDA

Copiar `addon/globalPlugins/cashflow/` al scratchpad de NVDA o empaquetar con la estructura de add-on cuando se agregue el build completo.

Validado contra documentacion de NVDA 2026.1.1.
