# Frame Structure Rules

Este dominio genera estructuras paramétricas aproximadas desde texto o imagen.

## Objetivo

No copiar exactamente una imagen, sino generar una hipótesis CAD editable y documentada.

## Casos soportados iniciales

- mesa industrial
- bastidor rectangular
- marco soldado simple
- soporte estructural simple
- carro metálico simple

## Operaciones CAD necesarias

- box
- square_tube_between_points
- boolean_fuse
- bom_report

## Reglas

1. Toda estructura debe tener dimensiones generales.
2. Todo perfil debe tener start y end.
3. Si faltan miembros, se genera una mesa básica por defecto.
4. Si no hay cotas, se usan supuestos razonables y se declaran.
5. La salida no debe considerarse fabricable sin revisión técnica.
6. Para fabricación real faltan: carga, material, soldadura, tolerancias y verificación estructural.

## Supuestos por defecto para mesa industrial

- Largo: 1200 mm
- Ancho: 700 mm
- Alto: 850 mm
- Cubierta: plancha 6 mm
- Perfil: tubo cuadrado 40x40x3 mm
