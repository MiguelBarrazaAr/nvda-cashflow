# Cashflow

Cashflow permite gestionar pagos y cobros desde NVDA.

## Interfaz principal

`NVDA+control+f` abre la interfaz principal con cuatro listas:

- pagos pendientes;
- pagos realizados;
- cobros pendientes;
- cobros realizados.

En una lista, pulsa `Intro` sobre un elemento para abrir sus acciones. En pendientes se puede marcar como realizado, editar o eliminar. En realizados se puede marcar como pendiente, editar o eliminar. Al eliminar siempre se pide confirmacion.

La interfaz principal se cierra con `Escape`.

## Gestos

- `pagos`: una pulsacion abre pendientes y realizados, dos pulsaciones agregan un pago y tres anuncian los pendientes del mes.
- `cobros`: una pulsacion abre pendientes y realizados, dos pulsaciones agregan un cobro y tres anuncian los pendientes del mes.
- `ingresos`: una pulsacion abre el gestor de ingresos, dos pulsaciones agregan un ingreso y tres anuncian el total de ingresos del mes.
- `informe`: abre un informe HTML del mes actual o del mes filtrado.

## Gestores

Desde la interfaz principal se puede abrir el gestor de pagos o el gestor de cobros. Cada gestor permite alta, baja y modificacion. Tambien se puede cerrar con `Escape`.
En los gestores se puede importar y exportar en `CSV`, `JSON` o `Excel` segun el formato elegido al guardar.

## Filtro mensual

La vista de pagos y cobros permite cambiar el filtro por mes y anio. El atajo `T` anuncia el filtro aplicado.

## Copias de seguridad

Cashflow permite guardar una copia de seguridad cifrada en `.data` con contraseña y recuperar luego esa copia sobrescribiendo los datos actuales.

## Menu de NVDA

El menu Herramientas, Cashflow, permite abrir pagos, cobros, ingresos, informes, ayuda y las copias de seguridad.

## Configuracion

En Opciones de NVDA, categoria Cashflow, se puede activar o desactivar sonidos y elegir la moneda usada al anunciar importes.

## Comandos

- `NVDA+control+f`: abre Cashflow.
- Doble pulsacion de `NVDA+control+f`: abre el dialogo para agregar un pago.

Los comandos para pendientes y realizados quedan disponibles en Gestos de entrada, categoria Cashflow, sin gesto por defecto.
