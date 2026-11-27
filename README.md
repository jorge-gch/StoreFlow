# StoreFlow — Sistema de Gestión y Control de Tienda

Sistema web administrativo desarrollado en **Python + Django**, **SQLite**, **Bootstrap 5** y **Chart.js** para la gestión integral de inventario, ventas (POS), compras a proveedores, cuentas por cobrar/pagar, flujo financiero y reportes exportables.

---

## Módulos Implementados

1. **Autenticación y Roles (`core`)**: Inicio/cierre de sesión, perfiles de usuario (`Administrador` y `Empleado`) con control de acceso por rol y dashboard principal dinámico.
2. **Inventario (`inventory`)**: CRUD de productos y categorías, SKU, alertas de stock mínimo y Kardex atómico de entradas/salidas.
3. **Clientes y Proveedores (`customers`, `suppliers`)**: Directorios comerciales con búsqueda, activación/desactivación y ficha detallada.
4. **Ventas / POS (`sales`)**: Punto de venta interactivo con carrito en tiempo real, descuento automático de inventario, numeración correlativa (`FAC-000001`), métodos de pago (Efectivo, Transferencia, Crédito, Pago Parcial) y anulación controlada con reversión de stock.
5. **Compras (`suppliers`)**: Registro de órdenes de compra (`COM-000001`), ingreso automático al inventario, actualización opcional de costos y anulación validada.
6. **Cuentas por Cobrar y Pagar (`customers`, `suppliers`)**: Generación automática de deudas en ventas/compras a crédito o pago parcial, registro de abonos individuales y control de saldos pendientes y vencimientos.
7. **Finanzas (`finance`)**: Control de ingresos y egresos por categoría, integración automática sin doble contabilización (las ventas/compras a crédito solo impactan caja al recibir o realizar abonos) y anulación histórica segura.
8. **Reportes (`reports`)**: Analítica filtrable por rango de fechas (Hoy, Últimos 7 días, Mes actual o personalizado), gráficas y exportación a **Excel (`.xlsx`)** y **PDF (`.pdf`)**.

---

## Requisitos e Instalación

- Python 3.11 o superior
- `pip` y `venv`

### 1. Clonar e iniciar entorno virtual

```bash
git clone <url-del-repositorio>
cd StoreFlow
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Aplicar migraciones y cargar datos iniciales

```bash
python manage.py migrate
python manage.py setup_initial_data
```

Esto crea las credenciales iniciales de prueba:
- **Administrador:** `admin` / `admin1234`
- **Empleado:** `empleado` / `empleado1234`

### 4. Ejecutar el servidor de desarrollo

```bash
python manage.py runserver
```

Accede en el navegador a: `http://127.0.0.1:8000/`

---

## Variables de Entorno (Opcional para Producción)

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `DJANGO_SECRET_KEY` | Clave secreta de Django | Clave de desarrollo |
| `DJANGO_DEBUG` | Modo depuración (`True`/`False`) | `True` |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos separados por coma | `127.0.0.1,localhost,testserver` |

---

## Pruebas Automatizadas

Para validar todo el sistema (modelos, inventario, ventas, compras, deudas, finanzas, reportes y flujo completo E2E):

```bash
python manage.py check
python manage.py test
```
